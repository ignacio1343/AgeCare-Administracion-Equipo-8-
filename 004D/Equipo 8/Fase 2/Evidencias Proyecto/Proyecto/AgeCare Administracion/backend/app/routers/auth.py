"""CU01 Iniciar sesión · CU02 Verificar segundo factor · activación de cuentas del staff."""
import io
from datetime import timedelta

import segno
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..audit import client_ip, registrar
from ..config import get_settings
from ..db import get_db, utcnow
from ..deps import current_staff, permisos_de
from ..errors import ApiError
from ..models import MiembroStaff, SesionStaff
from ..schemas import (ActivacionInfo, ActivarIn, LoginIn, LoginOut, MfaConfirmIn, MfaSetupOut, PerfilOut, RefreshIn,
                       TokensOut)
from ..security import (DUMMY_HASH, create_access_token, hash_password, new_opaque_token, new_totp_secret, sha256,
                        totp_uri, verify_password, verify_totp)

router = APIRouter(prefix="/auth", tags=["Autenticación"])


def perfil(db: Session, s: MiembroStaff) -> PerfilOut:
    return PerfilOut(
        **{k: getattr(s, k) for k in ("id_staff", "nombre_completo", "email", "codigo_rol", "estado", "mfa_requerido",
                                      "mfa_habilitado", "ultimo_acceso", "fecha_creacion")},
        rol_nombre=s.rol.nombre,
        permisos=permisos_de(db, s.codigo_rol),
        configurar_mfa=s.mfa_requerido and not s.mfa_habilitado,
    )


def _emitir_tokens(db: Session, staff: MiembroStaff, request: Request) -> TokensOut:
    st = get_settings()
    refresh = new_opaque_token()
    db.add(SesionStaff(id_staff=staff.id_staff, refresh_token_hash=sha256(refresh),
                       fecha_expiracion=utcnow() + timedelta(hours=st.refresh_token_hours), ip=client_ip(request)))
    return TokensOut(access_token=create_access_token(staff.id_staff, staff.codigo_rol), refresh_token=refresh,
                     expires_in=st.access_token_minutes * 60)


def _registrar_fallo(db: Session, staff: MiembroStaff | None, email: str, motivo: str, request: Request) -> None:
    st = get_settings()
    now = utcnow()
    if staff is not None:
        if staff.primer_intento_fallido is None or now - staff.primer_intento_fallido > timedelta(minutes=st.login_window_minutes):
            staff.primer_intento_fallido, staff.intentos_fallidos = now, 0
        staff.intentos_fallidos += 1
        if staff.intentos_fallidos >= st.max_login_attempts:
            staff.bloqueado_hasta = now + timedelta(minutes=st.lockout_minutes)
            staff.intentos_fallidos, staff.primer_intento_fallido = 0, None
    registrar(db, actor=None, accion="auth.login_fallido", tipo_entidad="miembro_staff",
              id_entidad=staff.id_staff if staff else None, despues={"email": email, "motivo": motivo}, request=request)
    db.commit()


@router.post("/login", response_model=LoginOut, summary="CU01 · Iniciar sesión (CU02 si tiene TOTP)")
def login(data: LoginIn, request: Request, db: Session = Depends(get_db)):
    email = data.email.lower()
    staff = db.scalar(select(MiembroStaff).where(MiembroStaff.email == email))
    now = utcnow()

    if staff and staff.bloqueado_hasta and staff.bloqueado_hasta > now:
        registrar(db, actor=None, accion="auth.login_bloqueado", tipo_entidad="miembro_staff", id_entidad=staff.id_staff,
                  request=request)
        db.commit()
        raise ApiError(423, "ACCOUNT_LOCKED", "Cuenta bloqueada 15 minutos por intentos fallidos repetidos.")

    # Siempre se verifica un hash (aunque el correo no exista) para no revelar si la cuenta existe
    ok = verify_password(data.password, staff.password_hash if staff else DUMMY_HASH)
    if not staff or not ok:
        _registrar_fallo(db, staff, email, "credenciales", request)
        raise ApiError(401, "INVALID_CREDENTIALS", "Correo o contraseña incorrectos.")

    if staff.estado != "activo":
        registrar(db, actor=None, accion="auth.login_rechazado", tipo_entidad="miembro_staff", id_entidad=staff.id_staff,
                  despues={"estado": staff.estado}, request=request)
        db.commit()
        raise ApiError(403, "ADMIN_DISABLED", "Esta cuenta de administración está desactivada o pendiente de activación.")

    if staff.mfa_habilitado:
        if not data.codigo_otp:
            raise ApiError(401, "OTP_REQUIRED", "Esta cuenta exige segundo factor. Envía tu código TOTP.")
        if not verify_totp(staff.secreto_mfa, data.codigo_otp):
            _registrar_fallo(db, staff, email, "otp", request)
            raise ApiError(401, "OTP_INVALID", "El código de verificación no es válido o expiró.")

    ultimo_previo = staff.ultimo_acceso
    staff.intentos_fallidos, staff.primer_intento_fallido, staff.bloqueado_hasta = 0, None, None
    staff.ultimo_acceso = now
    tokens = _emitir_tokens(db, staff, request)
    registrar(db, actor=staff, accion="auth.login", tipo_entidad="miembro_staff", id_entidad=staff.id_staff,
              request=request)
    db.commit()
    p = perfil(db, staff)
    p.ultimo_acceso = ultimo_previo
    return LoginOut(**tokens.model_dump(), staff=p)


@router.post("/refresh", response_model=TokensOut, summary="Rotar el refresh token")
def refresh(data: RefreshIn, request: Request, db: Session = Depends(get_db)):
    ses = db.scalar(select(SesionStaff).where(SesionStaff.refresh_token_hash == sha256(data.refresh_token)))
    invalido = ApiError(401, "INVALID_REFRESH", "La sesión no es válida o fue revocada. Inicia sesión de nuevo.")
    if ses is None:
        raise invalido
    now = utcnow()
    if ses.fecha_revocacion is not None:
        if ses.motivo_revocacion == "rotada":
            # Reutilización de un token ya rotado: posible robo -> se revocan todas sus sesiones
            db.execute(update(SesionStaff).where(SesionStaff.id_staff == ses.id_staff,
                                                 SesionStaff.fecha_revocacion.is_(None))
                       .values(fecha_revocacion=now, motivo_revocacion="reuso_detectado"))
            registrar(db, actor=None, accion="auth.reuso_refresh", tipo_entidad="miembro_staff", id_entidad=ses.id_staff,
                      request=request)
            db.commit()
        raise invalido
    staff = db.get(MiembroStaff, ses.id_staff)
    if ses.fecha_expiracion <= now or staff is None or staff.estado != "activo":
        raise invalido
    ses.fecha_revocacion, ses.motivo_revocacion = now, "rotada"
    tokens = _emitir_tokens(db, staff, request)
    db.commit()
    return tokens


@router.post("/logout", status_code=204, summary="Cerrar sesión")
def logout(data: RefreshIn, request: Request, staff: MiembroStaff = Depends(current_staff), db: Session = Depends(get_db)):
    ses = db.scalar(select(SesionStaff).where(SesionStaff.refresh_token_hash == sha256(data.refresh_token),
                                              SesionStaff.id_staff == staff.id_staff))
    if ses and ses.fecha_revocacion is None:
        ses.fecha_revocacion, ses.motivo_revocacion = utcnow(), "logout"
    registrar(db, actor=staff, accion="auth.logout", tipo_entidad="miembro_staff", id_entidad=staff.id_staff,
              request=request)
    db.commit()
    return Response(status_code=204)


@router.get("/me", response_model=PerfilOut, summary="Perfil y permisos del staff autenticado")
def me(staff: MiembroStaff = Depends(current_staff), db: Session = Depends(get_db)):
    return perfil(db, staff)


# ---------------------------------------------------------------- activación de cuenta
def _por_token(db: Session, token: str) -> MiembroStaff:
    staff = db.scalar(select(MiembroStaff).where(MiembroStaff.token_activacion_hash == sha256(token)))
    if (staff is None or staff.estado != "pendiente" or staff.token_activacion_expira is None
            or staff.token_activacion_expira < utcnow()):
        raise ApiError(410, "ACTIVATION_INVALID", "El enlace de activación no es válido o expiró. Pide uno nuevo a un admin.")
    return staff


@router.get("/activacion/{token}", response_model=ActivacionInfo, summary="Validar un enlace de activación")
def info_activacion(token: str, db: Session = Depends(get_db)):
    s = _por_token(db, token)
    return ActivacionInfo(nombre_completo=s.nombre_completo, email=s.email, mfa_requerido=s.mfa_requerido)


@router.post("/activacion", status_code=204, summary="Activar cuenta y definir contraseña")
def activar(data: ActivarIn, request: Request, db: Session = Depends(get_db)):
    s = _por_token(db, data.token)
    s.password_hash = hash_password(data.password)
    s.estado, s.fecha_activacion = "activo", utcnow()
    s.token_activacion_hash = s.token_activacion_expira = None
    registrar(db, actor=s, accion="staff.activar", tipo_entidad="miembro_staff", id_entidad=s.id_staff, request=request)
    db.commit()
    return Response(status_code=204)


# ---------------------------------------------------------------- segundo factor (TOTP)
@router.post("/mfa/configurar", response_model=MfaSetupOut, summary="Generar secreto TOTP (paso 1)")
def mfa_configurar(staff: MiembroStaff = Depends(current_staff), db: Session = Depends(get_db)):
    if staff.mfa_habilitado:
        raise ApiError(409, "MFA_ALREADY_ENABLED", "El segundo factor ya está activo en esta cuenta.")
    staff.secreto_mfa = new_totp_secret()
    db.commit()
    uri = totp_uri(staff.secreto_mfa, staff.email)
    buf = io.BytesIO()
    segno.make(uri, error="m").save(buf, kind="svg", scale=5, border=2, xmldecl=False)
    return MfaSetupOut(secreto=staff.secreto_mfa, otpauth_uri=uri, qr_svg=buf.getvalue().decode())


@router.post("/mfa/confirmar", response_model=PerfilOut, summary="Confirmar el código y activar TOTP (paso 2)")
def mfa_confirmar(data: MfaConfirmIn, request: Request, staff: MiembroStaff = Depends(current_staff),
                  db: Session = Depends(get_db)):
    if not verify_totp(staff.secreto_mfa, data.codigo_otp):
        raise ApiError(422, "OTP_INVALID", "El código de verificación no es válido o expiró.")
    staff.mfa_habilitado = True
    registrar(db, actor=staff, accion="auth.mfa_activado", tipo_entidad="miembro_staff", id_entidad=staff.id_staff,
              request=request)
    db.commit()
    return perfil(db, staff)
