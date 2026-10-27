"""CU16 Moderar contenido reportado: cola única de reseñas, fotos, mensajes y perfiles."""
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..audit import registrar
from ..db import get_db, utcnow
from ..deps import requiere
from ..errors import ApiError
from ..models import ElementoModeracion, MiembroStaff
from ..schemas import Page
from ..util import obtener, paginar

router = APIRouter(prefix="/moderacion", tags=["Moderación"])
LECTURA, ESCRITURA = requiere("moderacion", "lectura"), requiere("moderacion", "escritura")


class ElementoOut(BaseModel):
    id_elemento: int
    tipo_elemento: str
    contenido_reportado: str
    motivo_reporte: str | None
    es_reporte_seguridad: bool
    estado: str
    autor: str
    autor_rechazos_90d: int
    reportante: str | None
    motivo_rechazo: str | None
    nota_decision: str | None
    decisor: str | None
    fecha_creacion: datetime
    fecha_decision: datetime | None


class ResumenOut(BaseModel):
    pendientes: int
    pendientes_seguridad: int
    decididos_hoy: int


class DecisionIn(BaseModel):
    decision: Literal["aprobado", "rechazado"]
    motivo_rechazo: Literal["ofensivo", "spam", "privacidad", "fuera_de_tema", "otro"] | None = None
    nota_decision: str | None = Field(None, max_length=1000)


def _rechazos(db: Session, id_usuario: int) -> int:
    from datetime import timedelta
    return db.scalar(select(func.count()).where(ElementoModeracion.id_usuario_autor == id_usuario,
                                                ElementoModeracion.estado == "rechazado",
                                                ElementoModeracion.fecha_decision >= utcnow() - timedelta(days=90)))


def elemento_out(db: Session, e: ElementoModeracion) -> ElementoOut:
    return ElementoOut(id_elemento=e.id_elemento, tipo_elemento=e.tipo_elemento, contenido_reportado=e.contenido_reportado,
                       motivo_reporte=e.motivo_reporte, es_reporte_seguridad=e.es_reporte_seguridad, estado=e.estado,
                       autor=e.autor.nombre, autor_rechazos_90d=_rechazos(db, e.id_usuario_autor),
                       reportante=e.reportante.nombre if e.reportante else None, motivo_rechazo=e.motivo_rechazo,
                       nota_decision=e.nota_decision, decisor=e.decisor.nombre_completo if e.decisor else None,
                       fecha_creacion=e.fecha_creacion, fecha_decision=e.fecha_decision)


@router.get("/resumen", response_model=ResumenOut)
def resumen(_: MiembroStaff = Depends(LECTURA), db: Session = Depends(get_db)):
    hoy = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    return ResumenOut(
        pendientes=db.scalar(select(func.count()).where(ElementoModeracion.estado == "pendiente")),
        pendientes_seguridad=db.scalar(select(func.count()).where(ElementoModeracion.estado == "pendiente",
                                                                  ElementoModeracion.es_reporte_seguridad.is_(True))),
        decididos_hoy=db.scalar(select(func.count()).where(ElementoModeracion.fecha_decision >= hoy)))


@router.get("/cola", response_model=Page[ElementoOut], summary="Cola de moderación (seguridad primero)")
def cola(estado: str = "pendiente", tipo: str | None = None, page: int = Query(1, ge=1),
         page_size: int = Query(20, ge=1, le=100), _: MiembroStaff = Depends(LECTURA), db: Session = Depends(get_db)):
    stmt = select(ElementoModeracion)
    if estado:
        stmt = stmt.where(ElementoModeracion.estado == estado)
    if tipo:
        stmt = stmt.where(ElementoModeracion.tipo_elemento == tipo)
    orden = ([ElementoModeracion.es_reporte_seguridad.desc(), ElementoModeracion.fecha_creacion.asc()]
             if estado == "pendiente" else [ElementoModeracion.fecha_decision.desc()])
    return paginar(db, stmt.order_by(*orden), page, page_size, lambda e: elemento_out(db, e))


@router.post("/{id_elemento}/decision", response_model=ElementoOut, summary="CU16 · Aprobar o rechazar")
def decidir(id_elemento: int, data: DecisionIn, request: Request, staff: MiembroStaff = Depends(ESCRITURA),
            db: Session = Depends(get_db)):
    e = obtener(db, ElementoModeracion, id_elemento, "El elemento")
    if e.estado != "pendiente":
        raise ApiError(409, "ALREADY_MODERATED", "Este elemento ya fue moderado.")
    if data.decision == "rechazado":
        if not data.motivo_rechazo:
            raise ApiError(422, "REASON_REQUIRED", "Indica el motivo del rechazo.")
        if data.motivo_rechazo == "otro" and not (data.nota_decision and data.nota_decision.strip()):
            raise ApiError(422, "NOTE_REQUIRED", "Con el motivo «otro» debes escribir una nota.")
    e.estado = data.decision
    e.motivo_rechazo = data.motivo_rechazo if data.decision == "rechazado" else None
    e.nota_decision = (data.nota_decision or "").strip() or None
    e.id_staff_decisor, e.fecha_decision = staff.id_staff, utcnow()
    registrar(db, actor=staff, accion=f"moderacion.{'aprobar' if data.decision == 'aprobado' else 'rechazar'}",
              tipo_entidad="elemento_moderacion", id_entidad=e.id_elemento,
              despues={"decision": data.decision, "motivo": e.motivo_rechazo}, request=request)
    db.commit()
    db.refresh(e)
    return elemento_out(db, e)
