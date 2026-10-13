"""CU03 Gestionar cuentas y roles del staff · CU04 Consultar bitácora de auditoría."""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session, selectinload

from ..audit import diff, registrar
from ..config import get_settings
from ..db import get_db, utcnow
from ..deps import requiere
from ..errors import ApiError
from ..models import MiembroStaff, RegistroAuditoria, RolStaff, SesionStaff
from ..schemas import (AuditoriaOut, Page, RolOut, StaffCreatedOut, StaffCreateIn, StaffOut, StaffUpdateIn)
from ..security import new_opaque_token, sha256

router = APIRouter(tags=["Staff y auditoría"])

ESCRITURA = requiere("staff", "escritura")
LECTURA = requiere("staff", "lectura")


def _snap(s: MiembroStaff) -> dict:
    return {"nombre_completo": s.nombre_completo, "codigo_rol": s.codigo_rol, "estado": s.estado,
            "mfa_requerido": s.mfa_requerido}


def _nueva_invitacion(s: MiembroStaff) -> tuple[str, datetime]:
    st = get_settings()
    token = new_opaque_token()
    s.token_activacion_hash = sha256(token)
    s.token_activacion_expira = utcnow() + timedelta(hours=st.activation_hours)
    # El envío por correo se simula: el enlace se devuelve a quien crea la cuenta
    return f"{st.frontend_url.rstrip('/')}/activar?token={token}", s.token_activacion_expira


@router.get("/staff/roles", response_model=list[RolOut], summary="Roles internos y su matriz de permisos")
def roles(_: MiembroStaff = Depends(LECTURA), db: Session = Depends(get_db)):
    return db.scalars(select(RolStaff).options(selectinload(RolStaff.permisos)).order_by(RolStaff.codigo_rol)).unique().all()


@router.get("/staff", response_model=Page[StaffOut], summary="Listar cuentas del staff")
def listar(codigo_rol: str | None = None, estado: str | None = None, q: str | None = Query(None, max_length=120),
           page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
           _: MiembroStaff = Depends(LECTURA), db: Session = Depends(get_db)):
    stmt = select(MiembroStaff)
    if codigo_rol:
        stmt = stmt.where(MiembroStaff.codigo_rol == codigo_rol)
    if estado:
        stmt = stmt.where(MiembroStaff.estado == estado)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(func.lower(MiembroStaff.nombre_completo).like(like), MiembroStaff.email.like(like)))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    items = db.scalars(stmt.order_by(MiembroStaff.nombre_completo).offset((page - 1) * page_size).limit(page_size)).all()
    return Page(items=items, page=page, page_size=page_size, total=total)


@router.post("/staff", response_model=StaffCreatedOut, status_code=201, summary="Crear cuenta e invitación")
def crear(data: StaffCreateIn, request: Request, actor: MiembroStaff = Depends(ESCRITURA), db: Session = Depends(get_db)):
    email = data.email.lower()
    if email.split("@")[1] not in get_settings().allowed_domains:
        raise ApiError(422, "DOMAIN_NOT_ALLOWED", "El dominio del correo no está autorizado para cuentas de administración.")
    if db.scalar(select(MiembroStaff).where(MiembroStaff.email == email)):
        raise ApiError(409, "EMAIL_IN_USE", "Ya existe una cuenta de staff con ese correo.")
    s = MiembroStaff(nombre_completo=data.nombre_completo.strip(), email=email, codigo_rol=data.codigo_rol,
                     estado="pendiente",
                     mfa_requerido=data.mfa_requerido if data.mfa_requerido is not None else data.codigo_rol == "admin")
    enlace, expira = _nueva_invitacion(s)
    db.add(s)
    db.flush()
    registrar(db, actor=actor, accion="staff.crear", tipo_entidad="miembro_staff", id_entidad=s.id_staff,
              despues=_snap(s) | {"email": email}, request=request)
    db.commit()
    return StaffCreatedOut(staff=StaffOut.model_validate(s), enlace_activacion=enlace, activacion_expira=expira)


def _admins_activos(db: Session) -> int:
    return db.scalar(select(func.count()).where(MiembroStaff.codigo_rol == "admin", MiembroStaff.estado == "activo"))


@router.patch("/staff/{id_staff}", response_model=StaffOut, summary="Cambiar nombre, rol o estado")
def actualizar(id_staff: int, data: StaffUpdateIn, request: Request, actor: MiembroStaff = Depends(ESCRITURA),
               db: Session = Depends(get_db)):
    s = db.get(MiembroStaff, id_staff)
    if s is None:
        raise ApiError(404, "NOT_FOUND", "La cuenta de staff no existe.")
    antes = _snap(s)
    cambios = data.model_dump(exclude_unset=True, exclude_none=True)
    if cambios.get("estado") == "inactivo" and s.id_staff == actor.id_staff:
        raise ApiError(409, "CANNOT_DISABLE_SELF", "No puedes desactivar tu propia cuenta.")
    if cambios.get("estado") == "activo" and s.estado == "pendiente":
        raise ApiError(409, "PENDING_ACTIVATION", "La cuenta aún no se activa. Reenvía la invitación.")
    pierde_admin = s.codigo_rol == "admin" and s.estado == "activo" and (
        cambios.get("estado") == "inactivo" or cambios.get("codigo_rol", "admin") != "admin")
    if pierde_admin and _admins_activos(db) <= 1:
        raise ApiError(409, "LAST_ADMIN", "Debe existir al menos una cuenta activa con rol admin.")
    for k, v in cambios.items():
        setattr(s, k, v)
    if cambios.get("estado") == "inactivo" or "codigo_rol" in cambios:
        # Desactivar o cambiar el rol revoca todas las sesiones abiertas
        db.execute(update(SesionStaff).where(SesionStaff.id_staff == s.id_staff, SesionStaff.fecha_revocacion.is_(None))
                   .values(fecha_revocacion=utcnow(), motivo_revocacion="cambio_cuenta"))
    a, d = diff(antes, _snap(s))
    if d:
        registrar(db, actor=actor, accion="staff.actualizar", tipo_entidad="miembro_staff", id_entidad=s.id_staff,
                  antes=a, despues=d, request=request)
    db.commit()
    return s


@router.post("/staff/{id_staff}/invitacion", response_model=StaffCreatedOut, summary="Reenviar invitación")
def reenviar(id_staff: int, request: Request, actor: MiembroStaff = Depends(ESCRITURA), db: Session = Depends(get_db)):
    s = db.get(MiembroStaff, id_staff)
    if s is None:
        raise ApiError(404, "NOT_FOUND", "La cuenta de staff no existe.")
    if s.estado != "pendiente":
        raise ApiError(409, "ALREADY_ACTIVE", "La cuenta ya fue activada.")
    enlace, expira = _nueva_invitacion(s)
    registrar(db, actor=actor, accion="staff.reenviar_invitacion", tipo_entidad="miembro_staff", id_entidad=s.id_staff,
              request=request)
    db.commit()
    return StaffCreatedOut(staff=StaffOut.model_validate(s), enlace_activacion=enlace, activacion_expira=expira)


# ---------------------------------------------------------------- CU04 bitácora
@router.get("/auditoria", response_model=Page[AuditoriaOut], summary="CU04 · Consultar bitácora de auditoría")
def auditoria(accion: str | None = Query(None, max_length=60), tipo_entidad: str | None = None,
              id_staff_actor: int | None = None, desde: datetime | None = None, hasta: datetime | None = None,
              page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
              _: MiembroStaff = Depends(LECTURA), db: Session = Depends(get_db)):
    stmt = select(RegistroAuditoria)
    if accion:
        stmt = stmt.where(RegistroAuditoria.accion.like(f"{accion}%"))
    if tipo_entidad:
        stmt = stmt.where(RegistroAuditoria.tipo_entidad == tipo_entidad)
    if id_staff_actor:
        stmt = stmt.where(RegistroAuditoria.id_staff_actor == id_staff_actor)
    if desde:
        stmt = stmt.where(RegistroAuditoria.fecha_hora >= desde)
    if hasta:
        stmt = stmt.where(RegistroAuditoria.fecha_hora <= hasta)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(RegistroAuditoria.fecha_hora.desc(), RegistroAuditoria.id_registro.desc())
                      .offset((page - 1) * page_size).limit(page_size)).unique().all()
    items = [AuditoriaOut.model_validate(r).model_copy(update={"actor_nombre": r.actor.nombre_completo if r.actor else None})
             for r in rows]
    return Page(items=items, page=page, page_size=page_size, total=total)
