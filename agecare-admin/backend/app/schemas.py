"""Esquemas de entrada y salida (Pydantic v2)."""
from datetime import datetime
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

T = TypeVar("T")

RolStaffCode = Literal["admin", "analista", "soporte", "editor", "moderador"]
EstadoTicket = Literal["abierto", "en_curso", "esperando_usuario", "resuelto", "cerrado"]
Prioridad = Literal["baja", "media", "alta", "critica"]


class Page(BaseModel, Generic[T]):
    items: list[T]
    page: int
    page_size: int
    total: int


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------- auth
class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    codigo_otp: str | None = Field(default=None, pattern=r"^\d{6}$")


class StaffOut(ORM):
    id_staff: int
    nombre_completo: str
    email: str
    codigo_rol: str
    estado: str
    mfa_requerido: bool
    mfa_habilitado: bool
    ultimo_acceso: datetime | None
    fecha_creacion: datetime


class PerfilOut(StaffOut):
    rol_nombre: str
    permisos: dict[str, str]
    configurar_mfa: bool


class TokensOut(BaseModel):
    """El refresh token no va en el cuerpo: viaja solo en la cookie HttpOnly «aca_refresh»."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class LoginOut(TokensOut):
    staff: PerfilOut


def _password_ok(v: str) -> str:
    if len(v) < 8 or not any(c.isalpha() for c in v) or not any(c.isdigit() for c in v):
        raise ValueError("La contraseña debe tener al menos 8 caracteres, letras y números.")
    return v


class ActivarIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    password: str = Field(max_length=128)

    @field_validator("password")
    @classmethod
    def _valida_password(cls, v: str) -> str:
        return _password_ok(v)


class ActivacionInfo(BaseModel):
    nombre_completo: str
    email: str
    mfa_requerido: bool


class MfaSetupOut(BaseModel):
    secreto: str
    otpauth_uri: str
    qr_svg: str


class MfaConfirmIn(BaseModel):
    codigo_otp: str = Field(pattern=r"^\d{6}$")


# ---------------------------------------------------------------- staff
class PermisoOut(ORM):
    modulo: str
    nivel_acceso: str


class RolOut(ORM):
    codigo_rol: str
    nombre: str
    descripcion: str | None
    permisos: list[PermisoOut]


class StaffCreateIn(BaseModel):
    nombre_completo: str = Field(min_length=2, max_length=120)
    email: EmailStr
    codigo_rol: RolStaffCode
    mfa_requerido: bool | None = None


class StaffCreatedOut(BaseModel):
    staff: StaffOut
    enlace_activacion: str
    activacion_expira: datetime


class StaffUpdateIn(BaseModel):
    nombre_completo: str | None = Field(default=None, min_length=2, max_length=120)
    codigo_rol: RolStaffCode | None = None
    estado: Literal["activo", "inactivo"] | None = None
    mfa_requerido: bool | None = None


# ---------------------------------------------------------------- auditoría
class AuditoriaOut(ORM):
    id_registro: int
    fecha_hora: datetime
    accion: str
    tipo_entidad: str
    id_entidad: str | None
    valor_anterior: str | None
    valor_nuevo: str | None
    ip: str | None
    id_staff_actor: int | None
    actor_nombre: str | None = None


# ---------------------------------------------------------------- soporte
class Ref(BaseModel):
    id: int | str
    nombre: str


class SolicitanteOut(BaseModel):
    id_usuario: int | None
    nombre: str
    email: str | None
    perfiles: list[str]


class TicketOut(BaseModel):
    id_ticket: int
    numero: int
    asunto: str
    categoria: Ref
    prioridad: str
    estado: str
    canal: str
    solicitante: SolicitanteOut
    paciente: Ref | None
    asignado: Ref | None
    fecha_creacion: datetime
    fecha_actualizacion: datetime
    fecha_primera_respuesta: datetime | None
    fecha_resolucion: datetime | None
    fecha_cierre: datetime | None


class ContextoOut(BaseModel):
    estado_cuenta: str | None
    fecha_registro: datetime | None
    ultimo_acceso: datetime | None
    pacientes: list[Ref]
    tickets_previos: int


class EncuestaOut(ORM):
    fecha_envio: datetime
    fecha_respuesta: datetime | None
    puntaje: int | None
    comentario: str | None


class TicketDetailOut(TicketOut):
    descripcion: str
    contexto: ContextoOut
    respuestas_total: int
    encuesta: EncuestaOut | None
    transiciones_permitidas: list[str]


class TicketCreateIn(BaseModel):
    asunto: str = Field(min_length=5, max_length=160)
    descripcion: str = Field(min_length=1, max_length=8000)
    email_usuario: EmailStr
    codigo_categoria: str
    prioridad: Prioridad = "media"
    canal: Literal["telefono", "correo", "consola"] = "consola"
    id_paciente: int | None = None
    nombre_solicitante: str | None = Field(default=None, max_length=120)
    confirmar_sin_enlace: bool = False


class TicketUpdateIn(BaseModel):
    estado: EstadoTicket | None = None
    prioridad: Prioridad | None = None
    codigo_categoria: str | None = None
    id_staff_asignado: int | None = None


class RespuestaIn(BaseModel):
    cuerpo: str = Field(min_length=1, max_length=8000)
    es_interna: bool = False


class RespuestaOut(BaseModel):
    id_respuesta: int
    tipo_autor: str
    autor_nombre: str
    cuerpo: str
    es_interna: bool
    fecha: datetime


class CategoriaConteo(BaseModel):
    codigo: str
    nombre: str
    total: int


class IndicadoresOut(BaseModel):
    abiertos: int
    en_curso: int
    esperando_usuario: int
    resueltos_30d: int
    primera_respuesta_horas_prom: float | None
    resolucion_horas_prom: float | None
    csat_promedio: float | None
    csat_respuestas: int
    sin_asignar: int
    por_categoria_30d: list[CategoriaConteo]
