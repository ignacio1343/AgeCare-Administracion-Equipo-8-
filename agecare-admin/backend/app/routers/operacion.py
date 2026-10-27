"""Estado operativo y alertas: CU27 Monitorear componentes (+CU28) · CU29 Consultar estado operativo
· CU30 Monitorear alertas de la plataforma · CU31 Gestionar incidentes."""
from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..audit import diff, registrar
from ..db import get_db, utcnow
from ..deps import requiere
from ..errors import ApiError
from ..models import (TRANSICIONES_INCIDENTE, Alerta, Componente, Incidente, MiembroStaff, ProcesoCritico, TipoAlerta,
                      VerificacionSalud)
from ..monitor import ejecutar_ciclo
from ..schemas import Page
from ..util import obtener, paginar, snap

router = APIRouter(prefix="/operacion", tags=["Estado operativo"])
LECTURA = requiere("operacion", "lectura")
ESCRITURA = requiere("operacion", "escritura")


class ComponenteOut(BaseModel):
    codigo: str
    nombre: str
    tecnologia: str | None
    es_asincrono: bool
    estado: str
    estado_desde: datetime
    uptime_30d: float
    latencia_p50_ms: int | None
    latencia_p95_ms: int | None
    umbral_p95_ms: int
    ultima_verificacion: datetime | None


class ProcesoOut(BaseModel):
    codigo: str
    nombre: str
    cadena: str
    p95_segundos: float
    exito_24h: float
    estado: str
    componentes: list[str]


class IncidenteOut(BaseModel):
    id_incidente: int
    titulo: str
    componente: str | None
    componente_nombre: str | None
    severidad: str
    estado: str
    es_mantenimiento: bool
    creado_automaticamente: bool
    descripcion: str
    resolucion: str | None
    responsable: str | None
    fecha_inicio: datetime
    fecha_resolucion: datetime | None
    transiciones_permitidas: list[str]


class EstadoOut(BaseModel):
    estado_general: str
    resumen: str
    ultima_verificacion: datetime | None
    componentes: list[ComponenteOut]
    procesos: list[ProcesoOut]
    incidentes_abiertos: int


class IncidenteIn(BaseModel):
    titulo: str = Field(min_length=5, max_length=160)
    descripcion: str = Field(min_length=5, max_length=4000)
    severidad: Literal["degradado", "caido"]
    codigo_componente: str | None = None
    es_mantenimiento: bool = False


class IncidenteUpdateIn(BaseModel):
    estado: Literal["investigando", "en_observacion", "resuelto", "completado"] | None = None
    descripcion: str | None = Field(None, min_length=5, max_length=4000)
    resolucion: str | None = Field(None, min_length=5, max_length=2000)
    severidad: Literal["degradado", "caido"] | None = None
    id_staff_responsable: int | None = None


class AlertaTipoOut(BaseModel):
    codigo: str
    nombre: str
    total: int
    activas: int
    atencion_min_prom: float | None


class AlertaOut(BaseModel):
    id_alerta: int
    tipo: str
    paciente: str
    severidad: str
    estado: str
    fecha_emision: datetime
    fecha_atencion: datetime | None


class AlertasOut(BaseModel):
    horas: int
    total: int
    activas: int
    por_tipo: list[AlertaTipoOut]
    recientes: list[AlertaOut]


def _transiciones(i: Incidente) -> list[str]:
    if i.es_mantenimiento:
        return ["completado"] if i.estado not in ("completado", "resuelto") else []
    return sorted(TRANSICIONES_INCIDENTE[i.estado])


def incidente_out(i: Incidente) -> IncidenteOut:
    return IncidenteOut(id_incidente=i.id_incidente, titulo=i.titulo, componente=i.codigo_componente,
                        componente_nombre=i.componente.nombre if i.componente else None, severidad=i.severidad,
                        estado=i.estado, es_mantenimiento=i.es_mantenimiento,
                        creado_automaticamente=i.creado_automaticamente, descripcion=i.descripcion,
                        resolucion=i.resolucion, responsable=i.responsable.nombre_completo if i.responsable else None,
                        fecha_inicio=i.fecha_inicio, fecha_resolucion=i.fecha_resolucion,
                        transiciones_permitidas=_transiciones(i))


# ---------------------------------------------------------------- CU29
@router.get("/estado", response_model=EstadoOut, summary="CU29 · Consultar estado operativo")
def estado(_: MiembroStaff = Depends(LECTURA), db: Session = Depends(get_db)):
    ultimas = dict(db.execute(select(VerificacionSalud.codigo_componente, func.max(VerificacionSalud.fecha_hora))
                              .group_by(VerificacionSalud.codigo_componente)).all())
    comps = [ComponenteOut(codigo=c.codigo_componente, nombre=c.nombre, tecnologia=c.tecnologia, es_asincrono=c.es_asincrono,
                           estado=c.estado_actual, estado_desde=c.estado_desde, uptime_30d=float(c.uptime_30d),
                           latencia_p50_ms=c.latencia_p50_ms, latencia_p95_ms=c.latencia_p95_ms,
                           umbral_p95_ms=c.umbral_p95_ms, ultima_verificacion=ultimas.get(c.codigo_componente))
             for c in db.scalars(select(Componente).order_by(Componente.orden))]
    procesos = [ProcesoOut(codigo=p.codigo_proceso, nombre=p.nombre, cadena=p.cadena, p95_segundos=float(p.p95_segundos),
                           exito_24h=float(p.exito_24h), estado=p.estado,
                           componentes=[x.codigo_componente for x in p.componentes])
                for p in db.scalars(select(ProcesoCritico).order_by(ProcesoCritico.orden))]
    caidos = [c.nombre for c in comps if c.estado == "caido"]
    degradados = [c.nombre for c in comps if c.estado == "degradado"]
    if caidos:
        general, resumen = "caido", f"Interrupción: {', '.join(caidos)}"
    elif degradados:
        general, resumen = "degradado", f"{len(degradados)} componente(s) degradado(s): {', '.join(degradados)}"
    else:
        general, resumen = "operativo", "Todos los sistemas operativos"
    abiertos = db.scalar(select(func.count()).where(Incidente.estado.in_(("investigando", "en_observacion"))))
    ult = max(ultimas.values()) if ultimas else None
    return EstadoOut(estado_general=general, resumen=resumen, ultima_verificacion=ult, componentes=comps,
                     procesos=procesos, incidentes_abiertos=abiertos)


# ---------------------------------------------------------------- CU27 / CU28
@router.post("/monitor/ciclo", response_model=list[IncidenteOut],
             summary="CU27 · Ejecutar un ciclo de monitoreo ahora (lo hace el Planificador cada 60 s)")
def ciclo(simular_falla: str | None = Query(None, description="Código de componente a hacer fallar (demo)"),
          _: MiembroStaff = Depends(ESCRITURA), db: Session = Depends(get_db)):
    if simular_falla and db.get(Componente, simular_falla) is None:
        raise ApiError(404, "NOT_FOUND", "El componente no existe.")
    nuevos = ejecutar_ciclo(db, {simular_falla} if simular_falla else set())
    return [incidente_out(i) for i in nuevos]


# ---------------------------------------------------------------- CU31
@router.get("/incidentes", response_model=Page[IncidenteOut], summary="Incidentes y mantenimientos")
def incidentes(estado: str | None = None, dias: int = Query(30, ge=1, le=365), page: int = Query(1, ge=1),
               page_size: int = Query(20, ge=1, le=100), _: MiembroStaff = Depends(LECTURA), db: Session = Depends(get_db)):
    stmt = select(Incidente).where(Incidente.fecha_inicio >= utcnow() - timedelta(days=dias))
    if estado == "abiertos":
        stmt = stmt.where(Incidente.estado.in_(("investigando", "en_observacion")))
    elif estado:
        stmt = stmt.where(Incidente.estado == estado)
    return paginar(db, stmt.order_by(Incidente.fecha_inicio.desc()), page, page_size, incidente_out)


@router.post("/incidentes", response_model=IncidenteOut, status_code=201, summary="CU31 · Registrar incidente")
def crear_incidente(data: IncidenteIn, request: Request, staff: MiembroStaff = Depends(ESCRITURA),
                    db: Session = Depends(get_db)):
    if data.codigo_componente and db.get(Componente, data.codigo_componente) is None:
        raise ApiError(422, "VALIDATION_ERROR", "El componente no existe.")
    i = Incidente(**data.model_dump(), estado="investigando", id_staff_responsable=staff.id_staff)
    db.add(i)
    db.flush()
    registrar(db, actor=staff, accion="incidente.crear", tipo_entidad="incidente", id_entidad=i.id_incidente,
              despues=data.model_dump(), request=request)
    db.commit()
    db.refresh(i)
    return incidente_out(i)


@router.patch("/incidentes/{id_incidente}", response_model=IncidenteOut, summary="CU31 · Actualizar o resolver incidente")
def actualizar_incidente(id_incidente: int, data: IncidenteUpdateIn, request: Request,
                         staff: MiembroStaff = Depends(ESCRITURA), db: Session = Depends(get_db)):
    i = obtener(db, Incidente, id_incidente, "El incidente")
    campos = ["estado", "descripcion", "resolucion", "severidad", "id_staff_responsable"]
    antes = snap(i, campos)
    if i.estado in ("resuelto", "completado"):
        raise ApiError(409, "INCIDENT_CLOSED", "El incidente ya está cerrado.")
    cambios = data.model_dump(exclude_unset=True)
    nuevo = cambios.pop("estado", None)
    for k, v in cambios.items():
        if k == "id_staff_responsable" and v is not None and db.get(MiembroStaff, v) is None:
            raise ApiError(404, "NOT_FOUND", "El responsable no existe.")
        setattr(i, k, v)
    if nuevo and nuevo != i.estado:
        if nuevo not in _transiciones(i):
            raise ApiError(409, "INVALID_TRANSITION", f"Transición no permitida: {i.estado} → {nuevo}.",
                           {"permitidas": _transiciones(i)})
        if nuevo in ("resuelto", "completado"):
            if not i.resolucion:
                raise ApiError(422, "RESOLUTION_REQUIRED", "Para cerrar el incidente describe la resolución.")
            i.fecha_resolucion = utcnow()
        i.estado = nuevo
    i.fecha_actualizacion = utcnow()
    a, d = diff(antes, snap(i, campos))
    if d:
        registrar(db, actor=staff, accion="incidente.actualizar", tipo_entidad="incidente", id_entidad=i.id_incidente,
                  antes=a, despues=d, request=request)
    db.commit()
    db.refresh(i)
    return incidente_out(i)


# ---------------------------------------------------------------- CU30
@router.get("/alertas", response_model=AlertasOut, summary="CU30 · Monitorear alertas de la plataforma")
def alertas(horas: int = Query(24, ge=1, le=720), _: MiembroStaff = Depends(LECTURA), db: Session = Depends(get_db)):
    desde = utcnow() - timedelta(hours=horas)
    rows = db.scalars(select(Alerta).where(Alerta.fecha_emision >= desde).order_by(Alerta.fecha_emision.desc())).all()
    por_tipo = []
    for t in db.scalars(select(TipoAlerta).order_by(TipoAlerta.nombre)):
        de_tipo = [a for a in rows if a.codigo_tipo == t.codigo_tipo]
        tiempos = [(a.fecha_atencion - a.fecha_emision).total_seconds() / 60 for a in de_tipo if a.fecha_atencion]
        por_tipo.append(AlertaTipoOut(codigo=t.codigo_tipo, nombre=t.nombre, total=len(de_tipo),
                                      activas=sum(a.estado == "activa" for a in de_tipo),
                                      atencion_min_prom=round(sum(tiempos) / len(tiempos), 1) if tiempos else None))
    return AlertasOut(horas=horas, total=len(rows), activas=sum(a.estado == "activa" for a in rows), por_tipo=por_tipo,
                      recientes=[AlertaOut(id_alerta=a.id_alerta, tipo=a.tipo.nombre, paciente=a.paciente.nombre,
                                           severidad=a.severidad, estado=a.estado, fecha_emision=a.fecha_emision,
                                           fecha_atencion=a.fecha_atencion) for a in rows[:25]])
