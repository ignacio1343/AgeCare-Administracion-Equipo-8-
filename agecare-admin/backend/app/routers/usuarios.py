"""Gestión de usuarios de la app: CU32 Buscar usuarios y pacientes · CU33 Desactivar o reactivar cuenta
· CU34 Reenviar invitación · CU54 Crear representante, cuidador o residente · CU55 Asignar residentes
· CU56 Restablecer contraseña del portal.  Los datos son una réplica de la Plataforma AgeCare; las acciones se envían a ella."""
from datetime import date, datetime
from types import SimpleNamespace
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import false, func, or_, select
from sqlalchemy.orm import Session

from ..audit import registrar
from ..db import get_db, utcnow
from ..deps import requiere
from ..errors import ApiError
from ..models import MembresiaCirculo, MiembroStaff, Paciente, Ticket, UsuarioApp, UsuarioPerfil
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
    rut: str | None = None
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
    nombres: str | None = None
    primer_apellido: str | None = None
    segundo_apellido: str | None = None
    origen: str = "plataforma"
    acceso_portal: bool = False
    debe_cambiar_password: bool = False
    vistas_portal: list[str] = []
    id_paciente_propio: int | None = None
    fecha_aceptacion_terminos: datetime | None = None


class WhatsappIn(BaseModel):
    telefono: str | None = Field(None, max_length=25)
    whatsapp_habilitado: bool
    motivo: str = Field(min_length=5, max_length=300, description="Cómo se obtuvo el consentimiento o por qué se retira")


class EstadoIn(BaseModel):
    estado_cuenta: Literal["activa", "desactivada"]
    motivo: str = Field(min_length=5, max_length=300)


def _out(u: UsuarioApp) -> UsuarioOut:
    from ..rut import formatear
    return UsuarioOut(id_usuario=u.id_usuario, nombre=u.nombre, rut=formatear(u.rut), email=u.email, estado_cuenta=u.estado_cuenta,
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
        from ..rut import normalizar
        r = normalizar(q)
        stmt = stmt.where(or_(func.lower(UsuarioApp.nombre).like(like), func.lower(UsuarioApp.email).like(like),
                              UsuarioApp.id_usuario.in_(por_paciente), UsuarioApp.rut == r if r else false()))
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
    from ..portal import vistas_de
    propio = db.scalar(select(Paciente.id_paciente).where(Paciente.id_usuario == u.id_usuario))
    return UsuarioDetalleOut(
        **_out(u).model_dump(), tickets_total=total, tickets_abiertos=abiertos, telefono=u.telefono,
        whatsapp_habilitado=u.whatsapp_habilitado, whatsapp_verificado=u.whatsapp_verificado,
        nombres=u.nombres, primer_apellido=u.primer_apellido, segundo_apellido=u.segundo_apellido, origen=u.origen,
        acceso_portal=bool(u.password_hash), debe_cambiar_password=u.debe_cambiar_password, vistas_portal=vistas_de(u),
        id_paciente_propio=propio, fecha_aceptacion_terminos=u.fecha_aceptacion_terminos,
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


# ================================================================ v0.6 · cuentas del portal creadas por soporte
class NuevoUsuarioIn(BaseModel):
    perfil: Literal["representante", "cuidador", "residente"]
    rut: str = Field(max_length=14)
    nombres: str = Field(min_length=2, max_length=80, description="Para el residente: primer nombre")
    primer_apellido: str = Field(min_length=2, max_length=60)
    segundo_apellido: str | None = Field(None, max_length=60)
    email: EmailStr
    pais: str = Field("CL", max_length=2)
    telefono: str | None = Field(None, max_length=20)
    whatsapp_habilitado: bool = False
    fecha_nacimiento: date | None = None
    id_representante: int | None = Field(None, description="Residente: su representante (obligatorio)")
    codigo_plan: str = Field("gratuito", max_length=40, description="Residente: plan asignado por soporte (sin cobro)")
    id_pacientes: list[int] = Field(default_factory=list, max_length=20, description="Cuidador o representante: residentes")

    @field_validator("rut")
    @classmethod
    def _v_rut(cls, v):
        from .portal import _rut
        return _rut(v)

    @field_validator("nombres", "primer_apellido")
    @classmethod
    def _v_nom(cls, v):
        from .portal import _nombre
        return _nombre(v)

    @field_validator("segundo_apellido")
    @classmethod
    def _v_seg(cls, v):
        from .portal import _nombre
        return _nombre(v, False)


class NuevoUsuarioOut(BaseModel):
    usuario: UsuarioDetalleOut
    password_temporal: str
    mensaje: str


class AsignarIn(BaseModel):
    id_paciente: int


class RestablecerIn(BaseModel):
    motivo: str = Field(min_length=5, max_length=300, description="Cómo se validó la identidad (ticket, llamada…)")


class RestablecerOut(BaseModel):
    password_temporal: str
    mensaje: str


class ResidenteRefOut(BaseModel):
    id_paciente: int
    nombre: str
    rut: str | None
    plan: str | None
    representantes: list[str]
    cuidadores: list[str]


PERFIL_DE = {"representante": "familiar", "cuidador": "cuidadora", "residente": "adulto_mayor"}


def _asignar(db: Session, u: UsuarioApp, id_paciente: int) -> MembresiaCirculo:
    from ..portal import vistas_de
    vs = vistas_de(u)
    rol = "familiar" if "representante" in vs else "cuidadora" if "cuidador" in vs else None
    if rol is None:
        raise ApiError(409, "INVALID_PROFILE", "Solo se asignan residentes a representantes y cuidadores.")
    obtener(db, Paciente, id_paciente, "El residente")
    m = db.get(MembresiaCirculo, (u.id_usuario, id_paciente))
    now = utcnow()
    if m is None:
        m = MembresiaCirculo(id_usuario=u.id_usuario, id_paciente=id_paciente, rol_en_circulo=rol, estado="activo",
                             fecha_invitacion=now, fecha_aceptacion=now)
        db.add(m)
    elif m.estado == "activo" and m.rol_en_circulo == rol:
        raise ApiError(409, "ALREADY_ASSIGNED", "El residente ya está asignado a esta cuenta.")
    else:
        m.rol_en_circulo, m.estado, m.fecha_aceptacion = rol, "activo", now
    db.flush()
    return m


@router.get("/residentes/opciones", response_model=list[ResidenteRefOut], summary="Residentes para asignar (selector)")
def residentes_opciones(q: str | None = Query(None, max_length=120), _: MiembroStaff = Depends(LECTURA),
                        db: Session = Depends(get_db)):
    from ..portal import plan_vigente
    from ..rut import formatear, normalizar
    stmt = select(Paciente).where(Paciente.estado == "activo")
    if q:
        r = normalizar(q)
        stmt = stmt.where(or_(func.lower(Paciente.nombre).like(f"%{q.strip().lower()}%"), Paciente.rut == r if r else false()))
    out = []
    for p in db.scalars(stmt.order_by(Paciente.nombre).limit(50)):
        ms = db.scalars(select(MembresiaCirculo).where(MembresiaCirculo.id_paciente == p.id_paciente,
                                                       MembresiaCirculo.estado == "activo")).all()
        nom = {m.id_usuario: db.get(UsuarioApp, m.id_usuario).nombre for m in ms}
        out.append(ResidenteRefOut(id_paciente=p.id_paciente, nombre=p.nombre, rut=formatear(p.rut), plan=plan_vigente(db, p.id_paciente),
                                   representantes=[nom[m.id_usuario] for m in ms if m.rol_en_circulo == "familiar"],
                                   cuidadores=[nom[m.id_usuario] for m in ms if m.rol_en_circulo == "cuidadora"]))
    return out


@router.post("", response_model=NuevoUsuarioOut, status_code=201,
             summary="CU54 · Crear representante, cuidador o residente (con clave temporal para el portal)")
def crear_usuario(data: NuevoUsuarioIn, request: Request, staff: MiembroStaff = Depends(ESCRITURA),
                  db: Session = Depends(get_db)):
    from .. import portal
    from ..security import hash_password, password_temporal
    from ..whatsapp import enmascarar
    from .portal import _ocupado, telefono_e164
    from .portal_vistas import crear_residente
    clave = password_temporal()
    tel = telefono_e164(data.pais, data.telefono) if data.telefono else None
    if data.whatsapp_habilitado and not tel:
        raise ApiError(422, "VALIDATION_ERROR", "Para activar los avisos por WhatsApp se necesita un teléfono.",
                       [{"field": "telefono", "message": "Obligatorio para activar"}])
    if data.perfil == "residente":
        if not data.fecha_nacimiento or not data.id_representante:
            raise ApiError(422, "VALIDATION_ERROR", "El residente necesita fecha de nacimiento y representante.",
                           [{"field": "fecha_nacimiento" if not data.fecha_nacimiento else "id_representante",
                             "message": "Obligatorio"}])
        rep = obtener(db, UsuarioApp, data.id_representante, "El representante")
        if "representante" not in portal.vistas_de(rep):
            raise ApiError(422, "VALIDATION_ERROR", "La cuenta elegida no es un representante.",
                           [{"field": "id_representante", "message": "No es representante"}])
        plan = portal.plan_activo(db, data.codigo_plan)
        if plan is None:
            raise ApiError(404, "PLAN_NOT_FOUND", "El plan no existe o no está disponible.")

        datos = SimpleNamespace(rut=data.rut, primer_nombre=data.nombres, primer_apellido=data.primer_apellido,
                                segundo_apellido=data.segundo_apellido, email=data.email,
                                fecha_nacimiento=data.fecha_nacimiento)  # mismos campos que el formulario del portal
        p = crear_residente(db, datos, hash_password(clave), True, "consola")
        u = db.get(UsuarioApp, p.id_usuario)
        u.telefono = tel
        _asignar(db, rep, p.id_paciente)
        portal.nueva_suscripcion(db, portal.cuenta_familia(db, rep), plan.codigo_plan, p.id_paciente)
        extra = {"representante": rep.id_usuario, "plan": plan.codigo_plan}
    else:
        _ocupado(db, data.rut, data.email)
        u = UsuarioApp(nombre=portal.nombre_completo(data.nombres, data.primer_apellido, data.segundo_apellido),
                       nombres=data.nombres, primer_apellido=data.primer_apellido, segundo_apellido=data.segundo_apellido,
                       email=data.email.lower(), rut=data.rut, telefono=tel, password_hash=hash_password(clave),
                       debe_cambiar_password=True, origen="consola", whatsapp_habilitado=data.whatsapp_habilitado,
                       whatsapp_verificado=utcnow() if data.whatsapp_habilitado else None)
        db.add(u)
        db.flush()
        db.add(UsuarioPerfil(id_usuario=u.id_usuario, codigo_perfil=PERFIL_DE[data.perfil]))
        db.flush()
        db.refresh(u)
        if data.perfil == "representante":
            portal.cuenta_familia(db, u)
        for idp in dict.fromkeys(data.id_pacientes):
            _asignar(db, u, idp)
        extra = {"residentes": data.id_pacientes}
    registrar(db, actor=staff, accion="usuario_app.crear", tipo_entidad="usuario_app", id_entidad=u.id_usuario,
              despues={"perfil": data.perfil, "email": u.email, "telefono": enmascarar(tel), **extra}, request=request)
    db.commit()
    db.refresh(u)
    return NuevoUsuarioOut(usuario=detalle(u.id_usuario, staff, db), password_temporal=clave,
                           mensaje="Entrega la clave temporal al usuario: deberá cambiarla al entrar al portal.")


@router.post("/{id_usuario}/residentes", response_model=UsuarioDetalleOut, status_code=201,
             summary="CU55 · Asignar un residente a un representante o cuidador")
def asignar_residente(id_usuario: int, data: AsignarIn, request: Request, staff: MiembroStaff = Depends(ESCRITURA),
                      db: Session = Depends(get_db)):
    u = obtener(db, UsuarioApp, id_usuario, "El usuario")
    m = _asignar(db, u, data.id_paciente)
    registrar(db, actor=staff, accion="usuario_app.asignar_residente", tipo_entidad="membresia_circulo",
              id_entidad=f"{id_usuario}-{data.id_paciente}", despues={"rol": m.rol_en_circulo}, request=request)
    db.commit()
    db.refresh(u)
    return detalle(id_usuario, staff, db)


@router.delete("/{id_usuario}/residentes/{id_paciente}", response_model=UsuarioDetalleOut,
               summary="CU55 · Quitar un residente a un representante o cuidador")
def quitar_residente(id_usuario: int, id_paciente: int, request: Request, staff: MiembroStaff = Depends(ESCRITURA),
                     db: Session = Depends(get_db)):
    u = obtener(db, UsuarioApp, id_usuario, "El usuario")
    m = db.get(MembresiaCirculo, (id_usuario, id_paciente))
    if m is None or m.estado == "revocado":
        raise ApiError(404, "NOT_FOUND", "El residente no está asignado a esta cuenta.")
    m.estado = "revocado"
    registrar(db, actor=staff, accion="usuario_app.quitar_residente", tipo_entidad="membresia_circulo",
              id_entidad=f"{id_usuario}-{id_paciente}", antes={"estado": "activo"}, despues={"estado": "revocado"},
              request=request)
    db.commit()
    db.refresh(u)
    return detalle(id_usuario, staff, db)


@router.post("/{id_usuario}/restablecer-password", response_model=RestablecerOut,
             summary="CU56 · Restablecer la contraseña del portal (responde a «¿Olvidaste tu contraseña?»)")
def restablecer_password(id_usuario: int, data: RestablecerIn, request: Request, staff: MiembroStaff = Depends(ESCRITURA),
                         db: Session = Depends(get_db)):
    from sqlalchemy import update

    from ..models import SesionApp
    from ..security import hash_password, password_temporal
    u = obtener(db, UsuarioApp, id_usuario, "El usuario")
    clave = password_temporal()
    u.password_hash, u.debe_cambiar_password, u.intentos_fallidos, u.bloqueado_hasta = hash_password(clave), True, 0, None
    db.execute(update(SesionApp).where(SesionApp.id_usuario == id_usuario, SesionApp.fecha_revocacion.is_(None))
               .values(fecha_revocacion=utcnow(), motivo_revocacion="restablecida"))
    registrar(db, actor=staff, accion="usuario_app.restablecer_password", tipo_entidad="usuario_app", id_entidad=id_usuario,
              despues={"motivo": data.motivo}, request=request)
    db.commit()
    return RestablecerOut(password_temporal=clave,
                          mensaje="Clave temporal generada. Entrégala por teléfono: al entrar, el portal pedirá cambiarla.")
