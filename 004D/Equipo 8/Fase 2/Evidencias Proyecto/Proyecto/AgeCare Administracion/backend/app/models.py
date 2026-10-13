"""Modelo físico (subconjunto del MER v2 necesario para el Avance 2).

Los nombres de tablas y columnas siguen el MER y el diccionario de entidades.
Columnas marcadas como «físicas» no aparecen en el MER conceptual: son detalles
de implementación (hash de contraseña, secretos, contadores de bloqueo).
"""
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base, UTCDateTime, utcnow

# ---------------------------------------------------------------------------
# Dominios (valores permitidos)
# ---------------------------------------------------------------------------
ROLES_STAFF = ("admin", "analista", "soporte", "editor", "moderador")
ESTADOS_STAFF = ("pendiente", "activo", "inactivo")
NIVELES_ACCESO = ("lectura", "escritura")
MODULOS = ("metricas", "operacion", "soporte", "usuarios", "contenido", "marketplace",
           "moderacion", "comercial", "configuracion", "staff")

ESTADOS_TICKET = ("abierto", "en_curso", "esperando_usuario", "resuelto", "cerrado")
PRIORIDADES = ("baja", "media", "alta", "critica")
CANALES = ("app", "correo", "telefono", "consola")
TIPOS_AUTOR = ("staff", "usuario", "sistema")

# Transiciones válidas de un ticket (spec 8.4)
TRANSICIONES_TICKET: dict[str, set[str]] = {
    "abierto": {"en_curso"},
    "en_curso": {"esperando_usuario", "resuelto"},
    "esperando_usuario": {"en_curso"},
    "resuelto": {"cerrado", "en_curso"},
    "cerrado": set(),
}


def _in(col: str, values: tuple[str, ...]) -> str:
    return f"{col} IN ({', '.join(repr(v) for v in values)})"


# ---------------------------------------------------------------------------
# Acceso y auditoría
# ---------------------------------------------------------------------------
class RolStaff(Base):
    __tablename__ = "rol_staff"
    codigo_rol: Mapped[str] = mapped_column(String(40), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))
    descripcion: Mapped[str | None] = mapped_column(String(400))

    permisos: Mapped[list["PermisoRol"]] = relationship(back_populates="rol", cascade="all, delete-orphan")


class PermisoRol(Base):
    __tablename__ = "permiso_rol"
    modulo: Mapped[str] = mapped_column(String(40), primary_key=True)
    codigo_rol: Mapped[str] = mapped_column(ForeignKey("rol_staff.codigo_rol"), primary_key=True)
    nivel_acceso: Mapped[str] = mapped_column(String(30))
    __table_args__ = (CheckConstraint(_in("nivel_acceso", NIVELES_ACCESO), name="ck_permiso_nivel"),)

    rol: Mapped[RolStaff] = relationship(back_populates="permisos")


class MiembroStaff(Base):
    __tablename__ = "miembro_staff"
    id_staff: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    codigo_rol: Mapped[str] = mapped_column(ForeignKey("rol_staff.codigo_rol"))
    nombre_completo: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    estado: Mapped[str] = mapped_column(String(30), default="pendiente")
    mfa_requerido: Mapped[bool] = mapped_column(Boolean, default=False)
    mfa_habilitado: Mapped[bool] = mapped_column(Boolean, default=False)
    fecha_activacion: Mapped[datetime | None] = mapped_column(UTCDateTime)
    ultimo_acceso: Mapped[datetime | None] = mapped_column(UTCDateTime)
    fecha_creacion: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    # --- columnas físicas
    password_hash: Mapped[str | None] = mapped_column(String(255))
    secreto_mfa: Mapped[str | None] = mapped_column(String(64))
    intentos_fallidos: Mapped[int] = mapped_column(Integer, default=0)
    primer_intento_fallido: Mapped[datetime | None] = mapped_column(UTCDateTime)
    bloqueado_hasta: Mapped[datetime | None] = mapped_column(UTCDateTime)
    token_activacion_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    token_activacion_expira: Mapped[datetime | None] = mapped_column(UTCDateTime)

    __table_args__ = (CheckConstraint(_in("estado", ESTADOS_STAFF), name="ck_staff_estado"),)

    rol: Mapped[RolStaff] = relationship(lazy="joined")


class SesionStaff(Base):
    __tablename__ = "sesion_staff"
    id_sesion: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_staff: Mapped[int] = mapped_column(ForeignKey("miembro_staff.id_staff"), index=True)
    refresh_token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    fecha_inicio: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    fecha_expiracion: Mapped[datetime] = mapped_column(UTCDateTime)
    fecha_revocacion: Mapped[datetime | None] = mapped_column(UTCDateTime)
    motivo_revocacion: Mapped[str | None] = mapped_column(String(30))
    ip: Mapped[str | None] = mapped_column(String(45))


class RegistroAuditoria(Base):
    """Registro inmutable: la API solo inserta (no hay endpoint de edición ni borrado)."""

    __tablename__ = "registro_auditoria"
    id_registro: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_staff_actor: Mapped[int | None] = mapped_column(ForeignKey("miembro_staff.id_staff"), index=True)
    fecha_hora: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
    accion: Mapped[str] = mapped_column(String(60), index=True)
    tipo_entidad: Mapped[str] = mapped_column(String(40))
    id_entidad: Mapped[str | None] = mapped_column(String(40))
    valor_anterior: Mapped[str | None] = mapped_column(Text)
    valor_nuevo: Mapped[str | None] = mapped_column(Text)
    ip: Mapped[str | None] = mapped_column(String(45))

    actor: Mapped[MiembroStaff | None] = relationship(lazy="joined")


# ---------------------------------------------------------------------------
# Usuarios de la app (réplica mínima de la Plataforma AgeCare)
# ---------------------------------------------------------------------------
class PerfilApp(Base):
    __tablename__ = "perfil_app"
    codigo_perfil: Mapped[str] = mapped_column(String(40), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))


class UsuarioApp(Base):
    __tablename__ = "usuario_app"
    id_usuario: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    estado_cuenta: Mapped[str] = mapped_column(String(30), default="activa")
    fecha_registro: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    ultimo_acceso: Mapped[datetime | None] = mapped_column(UTCDateTime)

    perfiles: Mapped[list["UsuarioPerfil"]] = relationship(lazy="selectin")
    membresias: Mapped[list["MembresiaCirculo"]] = relationship(lazy="selectin")


class UsuarioPerfil(Base):
    __tablename__ = "usuario_perfil"
    id_usuario: Mapped[int] = mapped_column(ForeignKey("usuario_app.id_usuario"), primary_key=True)
    codigo_perfil: Mapped[str] = mapped_column(ForeignKey("perfil_app.codigo_perfil"), primary_key=True)
    fecha_asignacion: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    perfil: Mapped[PerfilApp] = relationship(lazy="joined")


class Paciente(Base):
    __tablename__ = "paciente"
    id_paciente: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(120))
    estado: Mapped[str] = mapped_column(String(30), default="activo")
    fecha_alta: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class MembresiaCirculo(Base):
    __tablename__ = "membresia_circulo"
    id_usuario: Mapped[int] = mapped_column(ForeignKey("usuario_app.id_usuario"), primary_key=True)
    id_paciente: Mapped[int] = mapped_column(ForeignKey("paciente.id_paciente"), primary_key=True)
    rol_en_circulo: Mapped[str] = mapped_column(String(30))
    estado: Mapped[str] = mapped_column(String(30), default="activo")
    fecha_invitacion: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    fecha_aceptacion: Mapped[datetime | None] = mapped_column(UTCDateTime)

    paciente: Mapped[Paciente] = relationship(lazy="joined")


# ---------------------------------------------------------------------------
# Soporte
# ---------------------------------------------------------------------------
class CategoriaTicket(Base):
    __tablename__ = "categoria_ticket"
    codigo_categoria: Mapped[str] = mapped_column(String(40), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))


class Ticket(Base):
    __tablename__ = "ticket"
    id_ticket: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    numero: Mapped[int | None] = mapped_column(Integer, unique=True, index=True)
    codigo_categoria: Mapped[str] = mapped_column(ForeignKey("categoria_ticket.codigo_categoria"))
    id_usuario: Mapped[int | None] = mapped_column(ForeignKey("usuario_app.id_usuario"), index=True)
    id_paciente: Mapped[int | None] = mapped_column(ForeignKey("paciente.id_paciente"))
    id_staff_asignado: Mapped[int | None] = mapped_column(ForeignKey("miembro_staff.id_staff"), index=True)
    asunto: Mapped[str] = mapped_column(String(160))
    descripcion: Mapped[str] = mapped_column(Text)
    prioridad: Mapped[str] = mapped_column(String(30), default="media")
    estado: Mapped[str] = mapped_column(String(30), default="abierto", index=True)
    canal: Mapped[str] = mapped_column(String(30), default="consola")
    fecha_creacion: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
    fecha_actualizacion: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)
    fecha_primera_respuesta: Mapped[datetime | None] = mapped_column(UTCDateTime)
    fecha_resolucion: Mapped[datetime | None] = mapped_column(UTCDateTime)
    fecha_cierre: Mapped[datetime | None] = mapped_column(UTCDateTime)
    nombre_solicitante: Mapped[str | None] = mapped_column(String(120))
    email_solicitante: Mapped[str | None] = mapped_column(String(150))

    __table_args__ = (
        CheckConstraint(_in("estado", ESTADOS_TICKET), name="ck_ticket_estado"),
        CheckConstraint(_in("prioridad", PRIORIDADES), name="ck_ticket_prioridad"),
        CheckConstraint(_in("canal", CANALES), name="ck_ticket_canal"),
    )

    categoria: Mapped[CategoriaTicket] = relationship(lazy="joined")
    usuario: Mapped[UsuarioApp | None] = relationship(lazy="joined")
    paciente: Mapped[Paciente | None] = relationship(lazy="joined")
    asignado: Mapped[MiembroStaff | None] = relationship(lazy="joined")
    respuestas: Mapped[list["RespuestaTicket"]] = relationship(
        back_populates="ticket", order_by="RespuestaTicket.fecha", cascade="all, delete-orphan")
    encuesta: Mapped["EncuestaSatisfaccion | None"] = relationship(back_populates="ticket", uselist=False, lazy="joined")


class RespuestaTicket(Base):
    __tablename__ = "respuesta_ticket"
    id_respuesta: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_ticket: Mapped[int] = mapped_column(ForeignKey("ticket.id_ticket"), index=True)
    id_staff_autor: Mapped[int | None] = mapped_column(ForeignKey("miembro_staff.id_staff"))
    cuerpo: Mapped[str] = mapped_column(Text)
    tipo_autor: Mapped[str] = mapped_column(String(30))
    es_interna: Mapped[bool] = mapped_column(Boolean, default=False)
    fecha: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    __table_args__ = (CheckConstraint(_in("tipo_autor", TIPOS_AUTOR), name="ck_respuesta_autor"),)

    ticket: Mapped[Ticket] = relationship(back_populates="respuestas")
    autor: Mapped[MiembroStaff | None] = relationship(lazy="joined")


class EncuestaSatisfaccion(Base):
    __tablename__ = "encuesta_satisfaccion"
    id_encuesta: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_ticket: Mapped[int] = mapped_column(ForeignKey("ticket.id_ticket"), unique=True)
    fecha_envio: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    fecha_respuesta: Mapped[datetime | None] = mapped_column(UTCDateTime)
    puntaje: Mapped[int | None] = mapped_column(Integer)
    comentario: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (CheckConstraint("puntaje IS NULL OR (puntaje BETWEEN 1 AND 5)", name="ck_encuesta_puntaje"),)

    ticket: Mapped[Ticket] = relationship(back_populates="encuesta")


# ===========================================================================
# SPRINT 3 · Estado operativo y alertas
# ===========================================================================
from datetime import date  # noqa: E402

from sqlalchemy import Date, Numeric  # noqa: E402

ESTADOS_COMPONENTE = ("operativo", "degradado", "caido")
ESTADOS_INCIDENTE = ("investigando", "en_observacion", "resuelto", "completado")
TRANSICIONES_INCIDENTE: dict[str, set[str]] = {
    "investigando": {"en_observacion", "resuelto"},
    "en_observacion": {"investigando", "resuelto"},
    "resuelto": set(),
    "completado": set(),
}


class Componente(Base):
    __tablename__ = "componente"
    codigo_componente: Mapped[str] = mapped_column(String(40), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))
    tecnologia: Mapped[str | None] = mapped_column(String(120))
    es_asincrono: Mapped[bool] = mapped_column(Boolean, default=False)
    estado_actual: Mapped[str] = mapped_column(String(30), default="operativo")
    uptime_30d: Mapped[float] = mapped_column(Numeric(7, 5), default=1)
    latencia_p50_ms: Mapped[int | None] = mapped_column(Integer)
    latencia_p95_ms: Mapped[int | None] = mapped_column(Integer)
    umbral_p95_ms: Mapped[int] = mapped_column(Integer, default=1000)  # física: umbral de degradación
    fallos_consecutivos: Mapped[int] = mapped_column(Integer, default=0)  # física
    estado_desde: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)  # física
    orden: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (CheckConstraint(_in("estado_actual", ESTADOS_COMPONENTE), name="ck_componente_estado"),)


class VerificacionSalud(Base):
    __tablename__ = "verificacion_salud"
    codigo_componente: Mapped[str] = mapped_column(ForeignKey("componente.codigo_componente"), primary_key=True)
    fecha_hora: Mapped[datetime] = mapped_column(UTCDateTime, primary_key=True)
    exitosa: Mapped[bool] = mapped_column(Boolean)
    latencia_ms: Mapped[int | None] = mapped_column(Integer)
    detalle: Mapped[str | None] = mapped_column(String(300))


class ProcesoCritico(Base):
    __tablename__ = "proceso_critico"
    codigo_proceso: Mapped[str] = mapped_column(String(40), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))
    cadena: Mapped[str] = mapped_column(String(300))
    p95_segundos: Mapped[float] = mapped_column(Numeric(9, 3), default=0)
    exito_24h: Mapped[float] = mapped_column(Numeric(7, 5), default=1)
    estado: Mapped[str] = mapped_column(String(30), default="operativo")
    orden: Mapped[int] = mapped_column(Integer, default=0)

    componentes: Mapped[list["ComponenteProceso"]] = relationship(lazy="selectin")


class ComponenteProceso(Base):
    __tablename__ = "componente_proceso"
    codigo_componente: Mapped[str] = mapped_column(ForeignKey("componente.codigo_componente"), primary_key=True)
    codigo_proceso: Mapped[str] = mapped_column(ForeignKey("proceso_critico.codigo_proceso"), primary_key=True)
    fecha_asignacion: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Incidente(Base):
    __tablename__ = "incidente"
    id_incidente: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    codigo_componente: Mapped[str | None] = mapped_column(ForeignKey("componente.codigo_componente"))
    id_staff_responsable: Mapped[int | None] = mapped_column(ForeignKey("miembro_staff.id_staff"))
    titulo: Mapped[str] = mapped_column(String(160))
    severidad: Mapped[str] = mapped_column(String(30))
    estado: Mapped[str] = mapped_column(String(30), default="investigando")
    es_mantenimiento: Mapped[bool] = mapped_column(Boolean, default=False)
    creado_automaticamente: Mapped[bool] = mapped_column(Boolean, default=False)
    descripcion: Mapped[str] = mapped_column(Text)
    resolucion: Mapped[str | None] = mapped_column(Text)
    fecha_inicio: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
    fecha_resolucion: Mapped[datetime | None] = mapped_column(UTCDateTime)
    fecha_actualizacion: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    __table_args__ = (
        CheckConstraint(_in("estado", ESTADOS_INCIDENTE), name="ck_incidente_estado"),
        CheckConstraint("severidad IN ('degradado', 'caido')", name="ck_incidente_severidad"),
    )

    componente: Mapped[Componente | None] = relationship(lazy="joined")
    responsable: Mapped[MiembroStaff | None] = relationship(lazy="joined")


class TipoAlerta(Base):
    __tablename__ = "tipo_alerta"
    codigo_tipo: Mapped[str] = mapped_column(String(40), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))
    severidad_por_defecto: Mapped[str] = mapped_column(String(30))


class Alerta(Base):
    __tablename__ = "alerta"
    id_alerta: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_paciente: Mapped[int] = mapped_column(ForeignKey("paciente.id_paciente"), index=True)
    codigo_tipo: Mapped[str] = mapped_column(ForeignKey("tipo_alerta.codigo_tipo"))
    fecha_emision: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
    severidad: Mapped[str] = mapped_column(String(30))
    estado: Mapped[str] = mapped_column(String(30), default="activa")
    fecha_atencion: Mapped[datetime | None] = mapped_column(UTCDateTime)

    tipo: Mapped[TipoAlerta] = relationship(lazy="joined")
    paciente: Mapped[Paciente] = relationship(lazy="joined")


class UmbralAlerta(Base):
    __tablename__ = "umbral_alerta"
    signo_vital: Mapped[str] = mapped_column(String(40), primary_key=True)
    nivel_semaforo: Mapped[str] = mapped_column(String(20), primary_key=True)
    codigo_tipo: Mapped[str] = mapped_column(ForeignKey("tipo_alerta.codigo_tipo"))
    valor_minimo: Mapped[float] = mapped_column(Numeric(10, 2))
    valor_maximo: Mapped[float] = mapped_column(Numeric(10, 2))
    unidad: Mapped[str] = mapped_column(String(20))
    fecha_actualizacion: Mapped[datetime | None] = mapped_column(UTCDateTime)
    __table_args__ = (
        CheckConstraint("nivel_semaforo IN ('verde', 'amarillo', 'rojo')", name="ck_umbral_nivel"),
        CheckConstraint("valor_minimo <= valor_maximo", name="ck_umbral_rango"),
    )


# ===========================================================================
# SPRINT 3 · Contenidos, productos, cuidadoras y moderación
# ===========================================================================
ESTADOS_PUBLICACION = ("borrador", "programado", "publicado", "archivado")


class Contenido(Base):
    __tablename__ = "contenido"
    id_contenido: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tipo: Mapped[str] = mapped_column(String(20))
    titulo: Mapped[str] = mapped_column(String(160))
    cuerpo: Mapped[str] = mapped_column(Text)
    etiquetas: Mapped[str | None] = mapped_column(String(400))  # separadas por coma
    estado: Mapped[str] = mapped_column(String(30), default="borrador")
    fecha_programada: Mapped[datetime | None] = mapped_column(UTCDateTime)
    fecha_publicacion: Mapped[datetime | None] = mapped_column(UTCDateTime)
    fecha_creacion: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)  # física
    fecha_eliminacion: Mapped[datetime | None] = mapped_column(UTCDateTime)  # física: borrado lógico
    __table_args__ = (
        CheckConstraint("tipo IN ('chiste', 'noticia')", name="ck_contenido_tipo"),
        CheckConstraint(_in("estado", ESTADOS_PUBLICACION), name="ck_contenido_estado"),
    )


class Producto(Base):
    __tablename__ = "producto"
    id_producto: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(160))
    categoria: Mapped[str] = mapped_column(String(60))
    proveedor: Mapped[str] = mapped_column(String(120))
    precio_referencial: Mapped[int | None] = mapped_column(Integer)
    url_externa: Mapped[str] = mapped_column(String(500))
    url_imagen: Mapped[str | None] = mapped_column(String(500))
    estado: Mapped[str] = mapped_column(String(30), default="borrador")
    fecha_creacion: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)  # física
    __table_args__ = (CheckConstraint("estado IN ('borrador', 'publicado', 'archivado')", name="ck_producto_estado"),)


class PerfilCuidadora(Base):
    __tablename__ = "perfil_cuidadora"
    id_perfil: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_usuario: Mapped[int] = mapped_column(ForeignKey("usuario_app.id_usuario"), unique=True)
    id_staff_revisor: Mapped[int | None] = mapped_column(ForeignKey("miembro_staff.id_staff"))
    zona: Mapped[str] = mapped_column(String(80))
    especialidades: Mapped[str | None] = mapped_column(String(400))
    idiomas: Mapped[str | None] = mapped_column(String(200))
    certificaciones_verificadas: Mapped[int] = mapped_column(Integer, default=0)
    calificacion_promedio: Mapped[float | None] = mapped_column(Numeric(3, 2))
    estado_publicacion: Mapped[str] = mapped_column(String(30), default="pendiente")
    motivo_estado: Mapped[str | None] = mapped_column(String(1000))
    fecha_envio: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    fecha_revision: Mapped[datetime | None] = mapped_column(UTCDateTime)
    __table_args__ = (CheckConstraint("estado_publicacion IN ('pendiente', 'aprobado', 'suspendido')", name="ck_cuidadora_estado"),)

    usuario: Mapped[UsuarioApp] = relationship(lazy="joined")
    revisor: Mapped[MiembroStaff | None] = relationship(lazy="joined")


MOTIVOS_RECHAZO = ("ofensivo", "spam", "privacidad", "fuera_de_tema", "otro")


class ElementoModeracion(Base):
    __tablename__ = "elemento_moderacion"
    id_elemento: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_usuario_autor: Mapped[int] = mapped_column(ForeignKey("usuario_app.id_usuario"), index=True)
    id_usuario_reportante: Mapped[int | None] = mapped_column(ForeignKey("usuario_app.id_usuario"))
    id_staff_decisor: Mapped[int | None] = mapped_column(ForeignKey("miembro_staff.id_staff"))
    tipo_elemento: Mapped[str] = mapped_column(String(30))
    contenido_reportado: Mapped[str] = mapped_column(Text)
    motivo_reporte: Mapped[str | None] = mapped_column(String(300))
    es_reporte_seguridad: Mapped[bool] = mapped_column(Boolean, default=False)
    estado: Mapped[str] = mapped_column(String(30), default="pendiente", index=True)
    motivo_rechazo: Mapped[str | None] = mapped_column(String(30))
    nota_decision: Mapped[str | None] = mapped_column(String(1000))
    fecha_decision: Mapped[datetime | None] = mapped_column(UTCDateTime)
    fecha_creacion: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    __table_args__ = (
        CheckConstraint("tipo_elemento IN ('resena', 'foto', 'mensaje', 'perfil')", name="ck_moderacion_tipo"),
        CheckConstraint("estado IN ('pendiente', 'aprobado', 'rechazado')", name="ck_moderacion_estado"),
        CheckConstraint("estado <> 'rechazado' OR motivo_rechazo IS NOT NULL", name="ck_moderacion_motivo"),
    )

    autor: Mapped[UsuarioApp] = relationship(foreign_keys=[id_usuario_autor], lazy="joined")
    reportante: Mapped[UsuarioApp | None] = relationship(foreign_keys=[id_usuario_reportante], lazy="joined")
    decisor: Mapped[MiembroStaff | None] = relationship(lazy="joined")


# ===========================================================================
# SPRINT 4 · Planes, suscripciones y pagos
# ===========================================================================
class Plan(Base):
    __tablename__ = "plan"
    codigo_plan: Mapped[str] = mapped_column(String(40), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))
    precio: Mapped[int] = mapped_column(Integer, default=0)
    moneda: Mapped[str] = mapped_column(String(3), default="CLP")
    unidad_facturable: Mapped[str] = mapped_column(String(20))
    periodicidad: Mapped[str] = mapped_column(String(20), default="mensual")
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    orden: Mapped[int] = mapped_column(Integer, default=0)

    funcionalidades: Mapped[list["PlanFuncionalidad"]] = relationship(lazy="selectin", cascade="all, delete-orphan")


class Funcionalidad(Base):
    __tablename__ = "funcionalidad"
    codigo_funcionalidad: Mapped[str] = mapped_column(String(40), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))
    uso_bajo_esperado: Mapped[bool] = mapped_column(Boolean, default=False)
    nota: Mapped[str | None] = mapped_column(String(300))
    orden: Mapped[int] = mapped_column(Integer, default=0)


class PlanFuncionalidad(Base):
    __tablename__ = "plan_funcionalidad"
    codigo_plan: Mapped[str] = mapped_column(ForeignKey("plan.codigo_plan"), primary_key=True)
    codigo_funcionalidad: Mapped[str] = mapped_column(ForeignKey("funcionalidad.codigo_funcionalidad"), primary_key=True)
    fecha_asignacion: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class CuentaCliente(Base):
    __tablename__ = "cuenta_cliente"
    id_cuenta: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_usuario: Mapped[int] = mapped_column(ForeignKey("usuario_app.id_usuario"), index=True)
    tipo_cuenta: Mapped[str] = mapped_column(String(20))
    nombre: Mapped[str] = mapped_column(String(120))
    email_facturacion: Mapped[str] = mapped_column(String(150))
    rut: Mapped[str | None] = mapped_column(String(12))
    estado: Mapped[str] = mapped_column(String(30), default="activa")
    fecha_creacion: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    __table_args__ = (CheckConstraint("tipo_cuenta IN ('familia', 'proveedor')", name="ck_cuenta_tipo"),)

    titular: Mapped[UsuarioApp] = relationship(lazy="joined")


class Suscripcion(Base):
    __tablename__ = "suscripcion"
    id_suscripcion: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_cuenta: Mapped[int] = mapped_column(ForeignKey("cuenta_cliente.id_cuenta"), index=True)
    codigo_plan: Mapped[str] = mapped_column(ForeignKey("plan.codigo_plan"))
    estado: Mapped[str] = mapped_column(String(30), default="activa")
    fecha_inicio: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    inicio_periodo: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    fin_periodo: Mapped[datetime] = mapped_column(UTCDateTime)
    fecha_cancelacion: Mapped[datetime | None] = mapped_column(UTCDateTime)
    motivo_cancelacion: Mapped[str | None] = mapped_column(String(300))
    id_externo_pasarela: Mapped[str | None] = mapped_column(String(100))
    __table_args__ = (CheckConstraint("estado IN ('activa', 'en_mora', 'cancelada', 'vencida')", name="ck_suscripcion_estado"),)

    cuenta: Mapped[CuentaCliente] = relationship(lazy="joined")
    plan: Mapped[Plan] = relationship(lazy="joined")


class TransaccionPago(Base):
    __tablename__ = "transaccion_pago"
    id_transaccion: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_suscripcion: Mapped[int] = mapped_column(ForeignKey("suscripcion.id_suscripcion"), index=True)
    monto: Mapped[int] = mapped_column(Integer)
    moneda: Mapped[str] = mapped_column(String(3), default="CLP")
    estado: Mapped[str] = mapped_column(String(30), default="pendiente")
    fecha: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
    medio_pago: Mapped[str | None] = mapped_column(String(60))
    codigo_error: Mapped[str | None] = mapped_column(String(60))
    id_externo_pasarela: Mapped[str | None] = mapped_column(String(100), unique=True)
    __table_args__ = (CheckConstraint("estado IN ('pendiente', 'aprobada', 'rechazada')", name="ck_transaccion_estado"),)

    suscripcion: Mapped[Suscripcion] = relationship(lazy="joined")
    reembolsos: Mapped[list["Reembolso"]] = relationship(lazy="selectin", back_populates="transaccion")


class Reembolso(Base):
    __tablename__ = "reembolso"
    id_reembolso: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_transaccion: Mapped[int] = mapped_column(ForeignKey("transaccion_pago.id_transaccion"), index=True)
    id_staff_autorizador: Mapped[int] = mapped_column(ForeignKey("miembro_staff.id_staff"))
    monto: Mapped[int] = mapped_column(Integer)
    motivo: Mapped[str] = mapped_column(String(300))
    estado: Mapped[str] = mapped_column(String(30), default="procesado")
    fecha: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    id_externo_pasarela: Mapped[str | None] = mapped_column(String(100))
    __table_args__ = (CheckConstraint("monto > 0", name="ck_reembolso_monto"),)

    transaccion: Mapped[TransaccionPago] = relationship(back_populates="reembolsos")
    autorizador: Mapped[MiembroStaff] = relationship(lazy="joined")


class EventoPago(Base):
    __tablename__ = "evento_pago"
    id_evento: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_transaccion: Mapped[int | None] = mapped_column(ForeignKey("transaccion_pago.id_transaccion"))
    id_externo_evento: Mapped[str] = mapped_column(String(100), unique=True)  # física: idempotencia
    tipo_evento: Mapped[str] = mapped_column(String(60))
    payload: Mapped[str | None] = mapped_column(Text)  # física
    fecha_recepcion: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    procesado: Mapped[bool] = mapped_column(Boolean, default=False)
    error_procesamiento: Mapped[str | None] = mapped_column(String(300))


# ===========================================================================
# SPRINT 4 · Métricas agregadas (las escribe el Planificador de tareas)
# ===========================================================================
class MetricaDiaria(Base):
    __tablename__ = "metrica_diaria"
    fecha: Mapped[date] = mapped_column(Date, primary_key=True)
    altas: Mapped[int] = mapped_column(Integer, default=0)
    bajas: Mapped[int] = mapped_column(Integer, default=0)
    descargas: Mapped[int] = mapped_column(Integer, default=0)
    usuarios_activos: Mapped[int] = mapped_column(Integer, default=0)
    usuarios_pago: Mapped[int] = mapped_column(Integer, default=0)
    mrr: Mapped[int] = mapped_column(Integer, default=0)


class SnapshotPlan(Base):
    __tablename__ = "snapshot_plan"
    fecha: Mapped[date] = mapped_column(Date, primary_key=True)
    codigo_plan: Mapped[str] = mapped_column(ForeignKey("plan.codigo_plan"), primary_key=True)
    usuarios: Mapped[int] = mapped_column(Integer)
    precio_congelado: Mapped[int | None] = mapped_column(Integer)
    mrr: Mapped[int] = mapped_column(Integer, default=0)
    churn_mensual: Mapped[float] = mapped_column(Numeric(7, 5), default=0)


class SnapshotEmbudo(Base):
    __tablename__ = "snapshot_embudo"
    fecha: Mapped[date] = mapped_column(Date, primary_key=True)
    descargas: Mapped[int] = mapped_column(Integer)
    cuentas_creadas: Mapped[int] = mapped_column(Integer)
    activos_30d: Mapped[int] = mapped_column(Integer)
    de_pago: Mapped[int] = mapped_column(Integer)


class ActividadPerfil(Base):
    __tablename__ = "actividad_perfil"
    ventana_dias: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo_perfil: Mapped[str] = mapped_column(ForeignKey("perfil_app.codigo_perfil"), primary_key=True)
    usuarios_activos: Mapped[int] = mapped_column(Integer)
    sesiones_semana: Mapped[float] = mapped_column(Numeric(7, 2))
    duracion_media_seg: Mapped[int] = mapped_column(Integer)
    retencion_30d: Mapped[float] = mapped_column(Numeric(7, 5))


class AdopcionFuncionalidad(Base):
    __tablename__ = "adopcion_funcionalidad"
    ventana_dias: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo_funcionalidad: Mapped[str] = mapped_column(ForeignKey("funcionalidad.codigo_funcionalidad"), primary_key=True)
    codigo_perfil: Mapped[str] = mapped_column(ForeignKey("perfil_app.codigo_perfil"), primary_key=True)
    usuarios: Mapped[int] = mapped_column(Integer)
    activos_del_perfil: Mapped[int] = mapped_column(Integer)
    adopcion: Mapped[float] = mapped_column(Numeric(7, 5))


class MetricaSoporteDiaria(Base):
    __tablename__ = "metrica_soporte_diaria"
    fecha: Mapped[date] = mapped_column(Date, primary_key=True)
    tickets_creados: Mapped[int] = mapped_column(Integer, default=0)
    tickets_resueltos: Mapped[int] = mapped_column(Integer, default=0)
    t_primera_respuesta_prom: Mapped[float | None] = mapped_column(Numeric(9, 2))  # horas
    t_resolucion_prom: Mapped[float | None] = mapped_column(Numeric(9, 2))  # horas
    csat_promedio: Mapped[float | None] = mapped_column(Numeric(4, 2))


# ===========================================================================
# SPRINT 5 · Configuración y legales
# ===========================================================================
class ParametroSistema(Base):
    __tablename__ = "parametro_sistema"
    clave: Mapped[str] = mapped_column(String(80), primary_key=True)
    descripcion: Mapped[str] = mapped_column(String(300))
    categoria: Mapped[str] = mapped_column(String(40))
    tipo_valor: Mapped[str] = mapped_column(String(20), default="numero")  # física: numero | texto | booleano
    valor: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)
    nota_cambio: Mapped[str | None] = mapped_column(String(500))
    fecha_actualizacion: Mapped[datetime | None] = mapped_column(UTCDateTime)


class VersionLegal(Base):
    __tablename__ = "version_legal"
    id_version: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_staff_autor: Mapped[int] = mapped_column(ForeignKey("miembro_staff.id_staff"))
    tipo_documento: Mapped[str] = mapped_column(String(20))
    version_mayor: Mapped[int] = mapped_column(Integer)
    version_menor: Mapped[int] = mapped_column(Integer)
    contenido: Mapped[str] = mapped_column(Text)
    registro_cambios: Mapped[str] = mapped_column(String(2000))
    fecha_vigencia: Mapped[date] = mapped_column(Date)
    requiere_reaceptacion: Mapped[bool] = mapped_column(Boolean, default=False)
    estado: Mapped[str] = mapped_column(String(30), default="borrador")
    fecha_publicacion: Mapped[datetime | None] = mapped_column(UTCDateTime)
    __table_args__ = (
        UniqueConstraint("tipo_documento", "version_mayor", "version_menor", name="uq_version_legal"),
        CheckConstraint("tipo_documento IN ('terminos', 'privacidad')", name="ck_legal_tipo"),
        CheckConstraint("estado IN ('borrador', 'publicada', 'reemplazada')", name="ck_legal_estado"),
    )

    autor: Mapped[MiembroStaff] = relationship(lazy="joined")
