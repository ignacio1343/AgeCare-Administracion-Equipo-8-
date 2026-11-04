"""Portal web · acceso: CU44 Registrarse como representante (con código por correo) · CU45 Iniciar sesión en el portal
· CU46 Recuperar contraseña (crea un ticket para soporte).

Sesión igual que la consola pero separada: access token de tipo «app» (15 min, en memoria) y refresh token rotativo
en la cookie HttpOnly `aca_portal` (ruta /api/v1/portal/auth). Un token de la consola no sirve en el portal ni al revés.
"""
import json
import re
from datetime import timedelta
import jwt
from fastapi import APIRouter, Depends, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from .. import correo, portal, rut as rutmod
from ..audit import client_ip, registrar
from ..config import get_settings
from ..db import get_db, utcnow
from ..errors import ApiError
from ..models import (CuentaCliente, NotificacionApp, SesionApp, Ticket, UsuarioApp, UsuarioPerfil, VerificacionCorreo,
                      VersionLegal)
from ..schemas import _password_ok
from ..security import (DUMMY_HASH, create_app_token, decode_app_token, hash_password, needs_rehash, new_opaque_token,
                        sha256, verify_password)
from ..whatsapp import enmascarar

router = APIRouter(prefix="/portal", tags=["Portal · acceso"])

COOKIE = "aca_portal"
COOKIE_PATH = "/api/v1/portal/auth"
CSRF_HEADER = "X-ACA-Refresh"
COD_INTENTOS, COD_ENVIOS, COD_ESPERA_SEG, COD_VIGENCIA_MIN = 3, 3, 60, 10
NOMBRE_RE = re.compile(r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ' .-]+$")

# País → (prefijo, nombre, patrón del número sin prefijo, ejemplo)
PAISES = {
    "CL": ("+56", "Chile", r"9\d{8}", "9 1234 5678"),
    "AR": ("+54", "Argentina", r"9?\d{10}", "9 11 2345 6789"),
    "PE": ("+51", "Perú", r"9\d{8}", "912 345 678"),
    "BO": ("+591", "Bolivia", r"[67]\d{7}", "7123 4567"),
    "CO": ("+57", "Colombia", r"3\d{9}", "312 345 6789"),
    "EC": ("+593", "Ecuador", r"9\d{8}", "99 123 4567"),
    "PY": ("+595", "Paraguay", r"9\d{8}", "981 234 567"),
    "UY": ("+598", "Uruguay", r"9\d{7}", "94 123 456"),
    "VE": ("+58", "Venezuela", r"4\d{9}", "412 345 6789"),
    "MX": ("+52", "México", r"\d{10}", "55 1234 5678"),
    "ES": ("+34", "España", r"[67]\d{8}", "612 34 56 78"),
    "US": ("+1", "Estados Unidos", r"[2-9]\d{9}", "201 555 0123"),
}

bearer = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------- dependencias
def usuario_portal(cred: HTTPAuthorizationCredentials | None = Depends(bearer),
                   db: Session = Depends(get_db)) -> UsuarioApp:
    expirada = ApiError(401, "UNAUTHORIZED", "Tu sesión expiró. Vuelve a iniciar sesión.")
    if cred is None:
        raise expirada
    try:
        data = decode_app_token(cred.credentials)
    except jwt.PyJWTError:
        raise expirada
    u = db.get(UsuarioApp, int(data["sub"]))
    if u is None or u.estado_cuenta != "activa":
        raise expirada
    return u


def vista(nombre: str | None = None):
    """Exige sesión del portal, contraseña definitiva y (si se indica) la vista del perfil."""
    def _check(u: UsuarioApp = Depends(usuario_portal)) -> UsuarioApp:
        if u.debe_cambiar_password:
            raise ApiError(403, "PASSWORD_CHANGE_REQUIRED", "Debes cambiar tu contraseña temporal antes de continuar.")
        if nombre and nombre not in portal.vistas_de(u):
            raise ApiError(403, "FORBIDDEN", "Tu cuenta no tiene acceso a esta sección del portal.")
        return u
    return _check


# ---------------------------------------------------------------- esquemas
class MeOut(BaseModel):
    id_usuario: int
    nombre: str
    nombres: str | None
    primer_apellido: str | None
    segundo_apellido: str | None
    email: str
    rut: str | None
    telefono: str | None
    vistas: list[str]
    debe_cambiar_password: bool
    whatsapp_habilitado: bool
    notificaciones_sin_leer: int


class LoginIn(BaseModel):
    usuario: str = Field(min_length=3, max_length=150, description="Correo o RUT")
    password: str = Field(min_length=1, max_length=128)


class LoginOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    usuario: MeOut


class TokensOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


def _nombre(v: str | None, obligatorio: bool = True) -> str | None:
    v = " ".join((v or "").split())
    if not v:
        if obligatorio:
            raise ValueError("Es obligatorio.")
        return None
    if not NOMBRE_RE.match(v):
        raise ValueError("Solo letras, espacios, apóstrofo o guion.")
    return v


def _rut(v: str) -> str:
    r = rutmod.normalizar(v)
    if r is None:
        raise ValueError("RUT inválido: revisa el número y el dígito verificador.")
    return r


class ClavesIn(BaseModel):
    password: str = Field(max_length=128)
    password2: str = Field(max_length=128)

    @field_validator("password")
    @classmethod
    def _p(cls, v):
        return _password_ok(v)

    @model_validator(mode="after")
    def _iguales(self):
        if self.password != self.password2:
            raise ValueError("Las contraseñas no coinciden.")
        return self


class RegistroIn(ClavesIn):
    email: EmailStr
    rut: str = Field(max_length=14)
    nombres: str = Field(min_length=2, max_length=80)
    primer_apellido: str = Field(min_length=2, max_length=60)
    segundo_apellido: str | None = Field(None, max_length=60)
    pais: str = Field(default="CL", max_length=2)
    telefono: str = Field(min_length=6, max_length=20)
    acepta_terminos: bool
    acepta_whatsapp: bool = False

    @field_validator("rut")
    @classmethod
    def _v_rut(cls, v):
        return _rut(v)

    @field_validator("nombres", "primer_apellido")
    @classmethod
    def _v_nom(cls, v):
        return _nombre(v)

    @field_validator("segundo_apellido")
    @classmethod
    def _v_seg(cls, v):
        return _nombre(v, False)

    @field_validator("acepta_terminos")
    @classmethod
    def _terminos(cls, v):
        if not v:
            raise ValueError("Debes aceptar los términos y la política de privacidad.")
        return v


class VerificacionOut(BaseModel):
    verificacion: str
    destino: str  # correo enmascarado al que se envió el código
    modo: str
    codigo_demo: str | None
    reenviar_en_seg: int
    expira_en_seg: int
    intentos_restantes: int


class ReenviarIn(BaseModel):
    verificacion: str = Field(min_length=10, max_length=100)


class ConfirmarIn(ReenviarIn):
    codigo: str = Field(pattern=r"^\d{6}$")


class OlvideIn(BaseModel):
    usuario: str = Field(min_length=3, max_length=150, description="Correo o RUT")
    detalle: str | None = Field(None, max_length=500)


class CambiarIn(ClavesIn):
    actual: str = Field(min_length=1, max_length=128)


class PaisOut(BaseModel):
    codigo: str
    prefijo: str
    nombre: str
    ejemplo: str


# ---------------------------------------------------------------- utilidades
def telefono_e164(pais: str, numero: str) -> str:
    if pais not in PAISES:
        raise ApiError(422, "VALIDATION_ERROR", "Selecciona un país de la lista.", [{"field": "pais", "message": "País no admitido"}])
    prefijo, nombre, patron, ejemplo = PAISES[pais]
    n = re.sub(r"\D", "", numero)
    if n.startswith(prefijo[1:]) and len(n) > len(prefijo[1:]) + 6:
        n = n[len(prefijo) - 1:]  # pegó el número con el prefijo
    if not re.fullmatch(patron, n):
        raise ApiError(422, "VALIDATION_ERROR", f"El teléfono no es válido para {nombre} (ejemplo: {ejemplo}).",
                       [{"field": "telefono", "message": f"Formato esperado: {prefijo} {ejemplo}"}])
    return prefijo + n


def buscar_por_identificador(db: Session, ident: str) -> UsuarioApp | None:
    ident = ident.strip()
    if "@" in ident:
        return db.scalar(select(UsuarioApp).where(func.lower(UsuarioApp.email) == ident.lower()))
    r = rutmod.normalizar(ident)
    return db.scalar(select(UsuarioApp).where(UsuarioApp.rut == r)) if r else None


def me_out(db: Session, u: UsuarioApp) -> MeOut:
    sin_leer = db.scalar(select(func.count()).where(NotificacionApp.id_usuario == u.id_usuario,
                                                    NotificacionApp.fecha_lectura.is_(None)))
    return MeOut(id_usuario=u.id_usuario, nombre=u.nombre, nombres=u.nombres, primer_apellido=u.primer_apellido,
                 segundo_apellido=u.segundo_apellido, email=u.email, rut=rutmod.formatear(u.rut),
                 telefono=enmascarar(u.telefono), vistas=portal.vistas_de(u), debe_cambiar_password=u.debe_cambiar_password,
                 whatsapp_habilitado=u.whatsapp_habilitado, notificaciones_sin_leer=sin_leer or 0)


def _set_cookie(response: Response, token: str) -> None:
    st = get_settings()
    response.set_cookie(COOKIE, token, max_age=st.refresh_token_hours * 3600, path=COOKIE_PATH, httponly=True,
                        secure=st.cookie_secure, samesite=st.cookie_samesite.lower())


def _emitir(db: Session, u: UsuarioApp, request: Request, response: Response) -> TokensOut:
    st = get_settings()
    refresh = new_opaque_token()
    db.add(SesionApp(id_usuario=u.id_usuario, refresh_token_hash=sha256(refresh), ip=client_ip(request),
                     fecha_expiracion=utcnow() + timedelta(hours=st.refresh_token_hours)))
    _set_cookie(response, refresh)
    return TokensOut(access_token=create_app_token(u.id_usuario), expires_in=st.access_token_minutes * 60)


def _refresh_de(request: Request) -> str | None:
    if request.headers.get(CSRF_HEADER) != "1":
        raise ApiError(403, "CSRF_HEADER_REQUIRED", f"Falta la cabecera {CSRF_HEADER}.")
    token = request.cookies.get(COOKIE)
    return token if token and 10 <= len(token) <= 200 else None


def _verificacion(db: Session, token: str) -> VerificacionCorreo:
    v = db.scalar(select(VerificacionCorreo).where(VerificacionCorreo.token_hash == sha256(token)))
    if v is None:
        raise ApiError(404, "VERIFICATION_NOT_FOUND", "El registro no existe. Vuelve a empezar.")
    if v.estado == "pendiente" and v.fecha_expiracion < utcnow():
        v.estado = "expirada"
        db.commit()
    if v.estado != "pendiente":
        raise ApiError(410, "VERIFICATION_CLOSED", {
            "verificada": "Este registro ya fue confirmado. Inicia sesión.",
            "bloqueada": "Superaste los intentos permitidos. Vuelve a registrarte.",
            "expirada": "El código venció. Vuelve a registrarte."}[v.estado])
    return v


def _verif_out(v: VerificacionCorreo, token: str, codigo: str | None) -> VerificacionOut:
    return VerificacionOut(verificacion=token, destino=correo.enmascarar(v.email), modo=v.proveedor,
                           codigo_demo=codigo if v.proveedor == "simulado" else None,
                           reenviar_en_seg=COD_ESPERA_SEG, expira_en_seg=COD_VIGENCIA_MIN * 60,
                           intentos_restantes=COD_INTENTOS - v.intentos)


def _ocupado(db: Session, rut: str | None, email: str | None) -> None:
    if rut and db.scalar(select(UsuarioApp.id_usuario).where(UsuarioApp.rut == rut)):
        raise ApiError(409, "RUT_EXISTS", "Este RUT ya tiene una cuenta. Inicia sesión o usa «¿Olvidaste tu contraseña?».",
                       [{"field": "rut", "message": "RUT ya registrado"}])
    if email and db.scalar(select(UsuarioApp.id_usuario).where(func.lower(UsuarioApp.email) == email.lower())):
        raise ApiError(409, "EMAIL_EXISTS", "Este correo ya tiene una cuenta. Inicia sesión o usa otro correo.",
                       [{"field": "email", "message": "Correo ya registrado"}])


# ---------------------------------------------------------------- registro del representante (CU44)
@router.get("/paises", response_model=list[PaisOut], summary="Países y prefijos telefónicos admitidos")
def paises():
    return [PaisOut(codigo=c, prefijo=p, nombre=n, ejemplo=e) for c, (p, n, _, e) in PAISES.items()]


@router.post("/registro", response_model=VerificacionOut, status_code=201,
             summary="CU44 · Registrarse como representante (paso 1: datos y envío del código por correo)")
def registro(data: RegistroIn, request: Request, db: Session = Depends(get_db)):
    tel = telefono_e164(data.pais, data.telefono)
    _ocupado(db, data.rut, data.email)
    now = utcnow()
    hace_1h = now - timedelta(hours=1)
    email = data.email.lower()
    if db.scalar(select(func.count()).where(VerificacionCorreo.email == email, VerificacionCorreo.fecha_creacion >= hace_1h)) >= 5 \
            or db.scalar(select(func.count()).where(VerificacionCorreo.ip == client_ip(request),
                                                    VerificacionCorreo.fecha_creacion >= hace_1h)) >= 10:
        raise ApiError(429, "RATE_LIMITED", "Demasiados registros desde este correo o red. Intenta en una hora.")
    codigo, codigo_hash = correo.nuevo_codigo()
    try:
        correo.enviar_codigo(email, data.nombres, codigo, COD_VIGENCIA_MIN)
    except correo.ErrorCorreo as e:
        raise ApiError(502, "EMAIL_ERROR", f"No pudimos enviar el correo con el código. {e}")
    terminos = db.scalar(select(VersionLegal.id_version).where(VersionLegal.tipo_documento == "terminos",
                                                               VersionLegal.estado == "publicada")
                         .order_by(VersionLegal.version_mayor.desc(), VersionLegal.version_menor.desc()).limit(1))
    token = new_opaque_token()
    v = VerificacionCorreo(token_hash=sha256(token), telefono=tel, rut=data.rut, email=email,
                           proveedor=correo.modo(), codigo_hash=codigo_hash, ip=client_ip(request),
                        fecha_expiracion=now + timedelta(minutes=COD_VIGENCIA_MIN),
                        datos=json.dumps({"nombres": data.nombres, "primer_apellido": data.primer_apellido,
                                          "segundo_apellido": data.segundo_apellido,
                                          "password_hash": hash_password(data.password),
                                          "acepta_whatsapp": data.acepta_whatsapp, "id_version_terminos": terminos}))
    db.add(v)
    db.commit()
    return _verif_out(v, token, codigo)


@router.post("/registro/reenviar", response_model=VerificacionOut, summary="CU44 · Reenviar el código (cada 60 s, máx. 3)")
def reenviar(data: ReenviarIn, db: Session = Depends(get_db)):
    v = _verificacion(db, data.verificacion)
    espera = COD_ESPERA_SEG - int((utcnow() - v.fecha_ultimo_envio).total_seconds())
    if espera > 0:
        raise ApiError(429, "RESEND_TOO_SOON", f"Espera {espera} segundos para pedir otro código.", {"espera_seg": espera})
    if v.envios >= COD_ENVIOS:
        raise ApiError(429, "RESEND_LIMIT", "Ya se enviaron 3 códigos. Vuelve a registrarte más tarde.")
    codigo, codigo_hash = correo.nuevo_codigo()
    try:
        correo.enviar_codigo(v.email, json.loads(v.datos).get("nombres", ""), codigo, COD_VIGENCIA_MIN)
    except correo.ErrorCorreo as e:
        raise ApiError(502, "EMAIL_ERROR", f"No pudimos enviar el correo con el código. {e}")
    v.codigo_hash = codigo_hash
    v.envios, v.intentos, v.fecha_ultimo_envio = v.envios + 1, 0, utcnow()
    v.fecha_expiracion = utcnow() + timedelta(minutes=COD_VIGENCIA_MIN)
    db.commit()
    return _verif_out(v, data.verificacion, codigo)


@router.post("/registro/confirmar", response_model=LoginOut, status_code=201,
             summary="CU44 · Confirmar el código del correo y crear la cuenta (paso 2)")
def confirmar(data: ConfirmarIn, request: Request, response: Response, db: Session = Depends(get_db)):
    v = _verificacion(db, data.verificacion)
    if not correo.comprobar(data.codigo, v.codigo_hash):
        v.intentos += 1
        if v.intentos >= COD_INTENTOS:
            v.estado = "bloqueada"
            db.commit()
            raise ApiError(429, "CODE_ATTEMPTS_EXCEEDED", "Superaste los 3 intentos. Vuelve a registrarte.")
        db.commit()
        restantes = COD_INTENTOS - v.intentos
        raise ApiError(422, "CODE_INVALID", f"Código incorrecto. Te quedan {restantes} intento{'s' if restantes > 1 else ''}.",
                       {"intentos_restantes": restantes})
    _ocupado(db, v.rut, v.email)  # alguien pudo registrarse con esos datos mientras tanto
    d = json.loads(v.datos)
    now = utcnow()
    u = UsuarioApp(nombre=portal.nombre_completo(d["nombres"], d["primer_apellido"], d["segundo_apellido"]),
                   nombres=d["nombres"], primer_apellido=d["primer_apellido"], segundo_apellido=d["segundo_apellido"],
                   email=v.email, rut=v.rut, telefono=v.telefono, password_hash=d["password_hash"], origen="portal",
                   whatsapp_habilitado=bool(d["acepta_whatsapp"]), whatsapp_verificado=now if d["acepta_whatsapp"] else None,
                   fecha_aceptacion_terminos=now, id_version_terminos=d.get("id_version_terminos"), ultimo_acceso=now)
    db.add(u)
    db.flush()
    db.add(UsuarioPerfil(id_usuario=u.id_usuario, codigo_perfil="familiar"))
    db.add(CuentaCliente(id_usuario=u.id_usuario, tipo_cuenta="familia", nombre=u.nombre,
                         email_facturacion=u.email, rut=u.rut))
    v.estado, v.fecha_verificacion, v.datos, v.codigo_hash = "verificada", now, "{}", None  # no se guarda la clave aquí
    portal.notificar(db, u.id_usuario, "sistema", "¡Bienvenido a AgeCare!",
                     "Elige el plan de tu residente y págalo para poder registrarlo.")
    registrar(db, actor=None, accion="portal.registro", tipo_entidad="usuario_app", id_entidad=u.id_usuario,
              despues={"email": u.email, "telefono": enmascarar(u.telefono), "whatsapp": u.whatsapp_habilitado,
                       "terminos": u.id_version_terminos}, request=request)
    tokens = _emitir(db, u, request, response)
    db.commit()
    db.refresh(u)
    return LoginOut(**tokens.model_dump(), usuario=me_out(db, u))


# ---------------------------------------------------------------- sesión (CU45)
@router.post("/auth/login", response_model=LoginOut, summary="CU45 · Iniciar sesión en el portal (correo o RUT)")
def login(data: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    st = get_settings()
    u = buscar_por_identificador(db, data.usuario)
    now = utcnow()
    if u and u.bloqueado_hasta and u.bloqueado_hasta > now:
        raise ApiError(423, "ACCOUNT_LOCKED", "Cuenta bloqueada 15 minutos por intentos fallidos repetidos.")
    ok = verify_password(data.password, u.password_hash if u and u.password_hash else DUMMY_HASH)
    if not u or not ok:
        if u is not None:
            u.intentos_fallidos += 1
            if u.intentos_fallidos >= st.max_login_attempts:
                u.bloqueado_hasta, u.intentos_fallidos = now + timedelta(minutes=st.lockout_minutes), 0
            db.commit()
        raise ApiError(401, "INVALID_CREDENTIALS", "Correo/RUT o contraseña incorrectos.")
    if u.estado_cuenta != "activa":
        raise ApiError(403, "ACCOUNT_DISABLED", "Tu cuenta está desactivada. Escribe a soporte para reactivarla.")
    if not portal.vistas_de(u):
        raise ApiError(403, "NO_PORTAL_VIEW", "Tu perfil todavía no tiene una vista en el portal web.")
    if needs_rehash(u.password_hash):
        u.password_hash = hash_password(data.password)
    u.intentos_fallidos, u.bloqueado_hasta, u.ultimo_acceso = 0, None, now
    tokens = _emitir(db, u, request, response)
    db.commit()
    return LoginOut(**tokens.model_dump(), usuario=me_out(db, u))


@router.post("/auth/refresh", response_model=TokensOut, summary="Rotar el refresh token del portal")
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    token = _refresh_de(request)
    invalido = ApiError(401, "INVALID_REFRESH", "La sesión no es válida o fue revocada. Inicia sesión de nuevo.")
    ses = db.scalar(select(SesionApp).where(SesionApp.refresh_token_hash == sha256(token))) if token else None
    if ses is None:
        raise invalido
    now = utcnow()
    if ses.fecha_revocacion is not None:
        if ses.motivo_revocacion == "rotada":  # reutilización de un token ya rotado: se revocan todas sus sesiones
            db.execute(update(SesionApp).where(SesionApp.id_usuario == ses.id_usuario, SesionApp.fecha_revocacion.is_(None))
                       .values(fecha_revocacion=now, motivo_revocacion="reuso_detectado"))
            db.commit()
        raise invalido
    u = db.get(UsuarioApp, ses.id_usuario)
    if ses.fecha_expiracion <= now or u is None or u.estado_cuenta != "activa":
        raise invalido
    ses.fecha_revocacion, ses.motivo_revocacion = now, "rotada"
    tokens = _emitir(db, u, request, response)
    db.commit()
    return tokens


@router.post("/auth/logout", status_code=204, summary="Cerrar sesión del portal")
def logout(request: Request, db: Session = Depends(get_db)):
    token = _refresh_de(request)
    ses = db.scalar(select(SesionApp).where(SesionApp.refresh_token_hash == sha256(token))) if token else None
    if ses and ses.fecha_revocacion is None:
        ses.fecha_revocacion, ses.motivo_revocacion = utcnow(), "logout"
        db.commit()
    resp = Response(status_code=204)
    st = get_settings()
    resp.delete_cookie(COOKIE, path=COOKIE_PATH, httponly=True, secure=st.cookie_secure, samesite=st.cookie_samesite.lower())
    return resp


@router.get("/auth/me", response_model=MeOut, summary="Datos de la cuenta y vistas disponibles")
def me(u: UsuarioApp = Depends(usuario_portal), db: Session = Depends(get_db)):
    return me_out(db, u)


@router.post("/auth/cambiar-password", response_model=MeOut, summary="Cambiar la contraseña (obligatorio si es temporal)")
def cambiar_password(data: CambiarIn, request: Request, u: UsuarioApp = Depends(usuario_portal),
                     db: Session = Depends(get_db)):
    if not verify_password(data.actual, u.password_hash):
        raise ApiError(422, "INVALID_PASSWORD", "La contraseña actual no es correcta.",
                       [{"field": "actual", "message": "Incorrecta"}])
    if data.password == data.actual:
        raise ApiError(422, "SAME_PASSWORD", "La nueva contraseña debe ser distinta de la actual.",
                       [{"field": "password", "message": "Igual a la actual"}])
    u.password_hash, u.debe_cambiar_password = hash_password(data.password), False
    registrar(db, actor=None, accion="portal.cambiar_password", tipo_entidad="usuario_app", id_entidad=u.id_usuario,
              request=request)
    db.commit()
    return me_out(db, u)


@router.post("/auth/olvide", status_code=202, summary="CU46 · ¿Olvidaste tu contraseña? (crea un ticket para soporte)")
def olvide(data: OlvideIn, request: Request, db: Session = Depends(get_db)):
    """Responde siempre lo mismo (no revela si la cuenta existe). Si existe, deja un ticket de «Acceso y cuenta» con
    canal App; soporte restablece la clave desde la consola y se la entrega al usuario por teléfono."""
    u = buscar_por_identificador(db, data.usuario)
    if u is not None and u.estado_cuenta == "activa":
        reciente = db.scalar(select(Ticket.id_ticket).where(
            Ticket.id_usuario == u.id_usuario, Ticket.codigo_categoria == "acceso_cuenta", Ticket.canal == "app",
            Ticket.asunto.like("Olvidé mi contraseña%"), Ticket.estado.in_(("abierto", "en_curso", "esperando_usuario")),
            Ticket.fecha_creacion >= utcnow() - timedelta(hours=24)).limit(1))
        if not reciente:
            vista_txt = ", ".join(portal.vistas_de(u)) or "sin vista"
            t = portal.crear_ticket(
                db, "acceso_cuenta", "Olvidé mi contraseña (portal web)",
                f"Solicitud desde «¿Olvidaste tu contraseña?» del portal ({vista_txt}). Identificador ingresado: "
                f"{data.usuario.strip()[:150]}.\n\nRestablecer la clave en Usuarios de la app → ficha → «Restablecer "
                f"contraseña» y entregarla por teléfono tras validar identidad."
                + (f"\n\nComentario del usuario: {data.detalle.strip()}" if data.detalle and data.detalle.strip() else ""),
                usuario=u, prioridad="alta")
            registrar(db, actor=None, accion="portal.olvide_password", tipo_entidad="ticket", id_entidad=t.numero,
                      request=request)
            db.commit()
    return {"mensaje": "Si los datos corresponden a una cuenta, soporte te contactará al teléfono o correo registrado "
                       "para restablecer tu contraseña."}


class WhatsappIn(BaseModel):
    habilitado: bool


@router.put("/me/whatsapp", response_model=MeOut, summary="Autorizar o retirar los avisos de riesgo por WhatsApp")
def mi_whatsapp(data: WhatsappIn, request: Request, u: UsuarioApp = Depends(vista("representante")),
                db: Session = Depends(get_db)):
    if data.habilitado and not u.telefono:
        raise ApiError(422, "PHONE_REQUIRED", "Tu cuenta no tiene teléfono. Pide a soporte que lo registre.")
    if data.habilitado != u.whatsapp_habilitado:
        u.whatsapp_habilitado = data.habilitado
        u.whatsapp_verificado = utcnow() if data.habilitado else None
        registrar(db, actor=None, accion="portal.whatsapp", tipo_entidad="usuario_app", id_entidad=u.id_usuario,
                  despues={"whatsapp_habilitado": data.habilitado, "telefono": enmascarar(u.telefono),
                           "origen": "portal"}, request=request)
        db.commit()
    return me_out(db, u)



class LegalOut(BaseModel):
    tipo_documento: str
    version: str
    fecha_vigencia: str
    contenido: str


@router.get("/legales", response_model=list[LegalOut], summary="Términos y política de privacidad vigentes (públicos)")
def legales(db: Session = Depends(get_db)):
    out = []
    for tipo in ("terminos", "privacidad"):
        v = db.scalar(select(VersionLegal).where(VersionLegal.tipo_documento == tipo, VersionLegal.estado == "publicada")
                      .order_by(VersionLegal.version_mayor.desc(), VersionLegal.version_menor.desc()).limit(1))
        if v:
            out.append(LegalOut(tipo_documento=tipo, version=f"{v.version_mayor}.{v.version_menor}",
                                fecha_vigencia=v.fecha_vigencia.isoformat(), contenido=v.contenido))
    return out
