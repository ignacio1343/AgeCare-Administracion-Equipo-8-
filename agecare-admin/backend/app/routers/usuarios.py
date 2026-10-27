"""Gestión de usuarios de la app: CU32 Buscar usuarios y pacientes · CU33 Desactivar o reactivar cuenta
· CU34 Reenviar invitación.  Los datos son una réplica de la Plataforma AgeCare; las acciones se envían a ella."""
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..audit import registrar
from ..db import get_db, utcnow
from ..deps import requiere
from ..errors import ApiError
from ..models import MembresiaCirculo, MiembroStaff, Paciente, Ticket, UsuarioApp
from ..schemas import Page
from ..util import obtener, paginar

router = APIRouter(prefix="/usuarios", tags=["Usuarios de la app"])
LECTURA = requiere("usuarios", "lectura")
ESCRITURA = requiere("usuarios", "escritura")


class MembresiaOut(BaseModel):
    id_paciente: int
    paciente: str
    rol_en_circulo: str
    estado: str
    fecha_invitacion: datetime
    fecha_aceptacion: datetime | None


class UsuarioOut(BaseModel):
    id_usuario: int
    nombre: str
    email: str
    estado_cuenta: str
    perfiles: list[str]
    pacientes: list[str]
    fecha_registro: datetime
    ultimo_acceso: datetime | None


class UsuarioDetalleOut(UsuarioOut):
    membresias: list[MembresiaOut]
    tickets_total: int
    tickets_abiertos: int
    telefono: str | None
    whatsapp_habilitado: bool
    whatsapp_verificado: datetime | None


class WhatsappIn(BaseModel):
    telefono: str | None = Field(None, max_length=25)
    whatsapp_habilitado: bool
    motivo: str = Field(min_length=5, max_length=300, description="Cómo se obtuvo el consentimiento o por qué se retira")


class EstadoIn(BaseModel):
    estado_cuenta: Literal["activa", "desactivada"]
    motivo: str = Field(min_length=5, max_length=300)


def _out(u: UsuarioApp) -> UsuarioOut:
    return UsuarioOut(id_usuario=u.id_usuario, nombre=u.nombre, email=u.email, estado_cuenta=u.estado_cuenta,
                      perfiles=[p.codigo_perfil for p in u.perfiles],
                      pacientes=[m.paciente.nombre for m in u.membresias],
                      fecha_registro=u.fecha_registro, ultimo_acceso=u.ultimo_acceso)


@router.get("", response_model=Page[UsuarioOut], summary="CU32 · Buscar usuarios y pacientes")
def buscar(q: str | None = Query(None, max_length=120), perfil: str | None = None, estado: str | None = None,
           page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
           _: MiembroStaff = Depends(LECTURA), db: Session = Depends(get_db)):
    stmt = select(UsuarioApp)
    if q:
        like = f"%{q.strip().lower()}%"
        por_paciente = (select(MembresiaCirculo.id_usuario).join(Paciente)
                        .where(func.lower(Paciente.nombre).like(like)))
        stmt = stmt.where(or_(func.lower(UsuarioApp.nombre).like(like), func.lower(UsuarioApp.email).like(like),
                              UsuarioApp.id_usuario.in_(por_paciente)))
    if perfil:
        from ..models import UsuarioPerfil
        stmt = stmt.where(UsuarioApp.id_usuario.in_(select(UsuarioPerfil.id_usuario)
                                                     .where(UsuarioPerfil.codigo_perfil == perfil)))
    if estado:
        stmt = stmt.where(UsuarioApp.estado_cuenta == estado)
    return paginar(db, stmt.order_by(UsuarioApp.nombre), page, page_size, _out)


@router.get("/{id_usuario}", response_model=UsuarioDetalleOut, summary="Ficha del usuario con sus membresías")
def detalle(id_usuario: int, _: MiembroStaff = Depends(LECTURA), db: Session = Depends(get_db)):
    u = obtener(db, UsuarioApp, id_usuario, "El usuario")
    total = db.scalar(select(func.count()).where(Ticket.id_usuario == id_usuario))
    abiertos = db.scalar(select(func.count()).where(Ticket.id_usuario == id_usuario,
                                                    Ticket.estado.in_(("abierto", "en_curso", "esperando_usuario"))))
    return UsuarioDetalleOut(
        **_out(u).model_dump(), tickets_total=total, tickets_abiertos=abiertos, telefono=u.telefono,
        whatsapp_habilitado=u.whatsapp_habilitado, whatsapp_verificado=u.whatsapp_verificado,
        membresias=[MembresiaOut(id_paciente=m.id_paciente, paciente=m.paciente.nombre, rol_en_circulo=m.rol_en_circulo,
                                 estado=m.estado, fecha_invitacion=m.fecha_invitacion, fecha_aceptacion=m.fecha_aceptacion)
                    for m in u.membresias])


@router.patch("/{id_usuario}/estado", response_model=UsuarioOut, summary="CU33 · Desactivar o reactivar cuenta")
def cambiar_estado(id_usuario: int, data: EstadoIn, request: Request, staff: MiembroStaff = Depends(ESCRITURA),
                   db: Session = Depends(get_db)):
    u = obtener(db, UsuarioApp, id_usuario, "El usuario")
    if u.estado_cuenta == data.estado_cuenta:
        raise ApiError(409, "NO_CHANGE", f"La cuenta ya está {data.estado_cuenta}.")
    antes = u.estado_cuenta
    u.estado_cuenta = data.estado_cuenta  # en producción: llamada a la API de la Plataforma AgeCare
    registrar(db, actor=staff, accion="usuario_app.estado", tipo_entidad="usuario_app", id_entidad=u.id_usuario,
              antes={"estado_cuenta": antes}, despues={"estado_cuenta": u.estado_cuenta, "motivo": data.motivo},
              request=request)
    db.commit()
    return _out(u)


@router.post("/{id_usuario}/membresias/{id_paciente}/invitacion", response_model=MembresiaOut,
             summary="CU34 · Reenviar invitación al círculo de cuidado")
def reenviar_invitacion(id_usuario: int, id_paciente: int, request: Request, staff: MiembroStaff = Depends(ESCRITURA),
                        db: Session = Depends(get_db)):
    m = db.get(MembresiaCirculo, (id_usuario, id_paciente))
    if m is None:
        raise ApiError(404, "NOT_FOUND", "La membresía no existe.")
    if m.estado != "invitado":
        raise ApiError(409, "INVITATION_NOT_PENDING", "La invitación ya fue aceptada o revocada.")
    m.fecha_invitacion = utcnow()  # envío por correo simulado
    registrar(db, actor=staff, accion="usuario_app.reenviar_invitacion", tipo_entidad="membresia_circulo",
              id_entidad=f"{id_usuario}-{id_paciente}", request=request)
    db.commit()
    return MembresiaOut(id_paciente=m.id_paciente, paciente=m.paciente.nombre, rol_en_circulo=m.rol_en_circulo,
                        estado=m.estado, fecha_invitacion=m.fecha_invitacion, fecha_aceptacion=m.fecha_aceptacion)


@router.put("/{id_usuario}/whatsapp", response_model=UsuarioDetalleOut,
            summary="Teléfono y consentimiento para avisos de salud por WhatsApp")
def configurar_whatsapp(id_usuario: int, data: WhatsappIn, request: Request, staff: MiembroStaff = Depends(ESCRITURA),
                        db: Session = Depends(get_db)):
    from ..whatsapp import enmascarar, normalizar_telefono
    u = obtener(db, UsuarioApp, id_usuario, "El usuario")
    tel = normalizar_telefono(data.telefono) if data.telefono else None
    if data.telefono and tel is None:
        raise ApiError(422, "VALIDATION_ERROR", "El teléfono debe tener formato internacional, p. ej. +56 9 1234 5678.",
                       [{"field": "telefono", "message": "Formato inválido"}])
    if data.whatsapp_habilitado and not tel:
        raise ApiError(422, "VALIDATION_ERROR", "Para activar los avisos se necesita un teléfono.",
                       [{"field": "telefono", "message": "Obligatorio para activar"}])
    antes = {"telefono": enmascarar(u.telefono), "whatsapp_habilitado": u.whatsapp_habilitado}
    if data.whatsapp_habilitado and (not u.whatsapp_habilitado or tel != u.telefono):
        u.whatsapp_verificado = utcnow()  # nuevo consentimiento (o para un número distinto)
    if not data.whatsapp_habilitado:
        u.whatsapp_verificado = None
    u.telefono, u.whatsapp_habilitado = tel, data.whatsapp_habilitado
    registrar(db, actor=staff, accion="usuario_app.whatsapp", tipo_entidad="usuario_app", id_entidad=u.id_usuario,
              antes=antes, despues={"telefono": enmascarar(tel), "whatsapp_habilitado": u.whatsapp_habilitado,
                                    "motivo": data.motivo}, request=request)
    db.commit()
    return detalle(id_usuario, staff, db)
