"""Avisos de salud por WhatsApp al familiar: CU41 Registrar evento de salud (actor Plataforma AgeCare)
· CU42 Avisar al familiar por WhatsApp (actor secundario WhatsApp Business) · CU43 Consultar avisos enviados."""
import json
from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Query, Request, Response
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .. import whatsapp as wa
from ..audit import registrar
from ..config import get_settings
from ..db import SessionLocal, get_db, utcnow
from ..deps import requiere
from ..errors import ApiError
from ..models import MembresiaCirculo, MensajeWhatsapp, MiembroStaff, Paciente, Plan, PlanFuncionalidad, UsuarioApp
from ..schemas import Page
from ..util import obtener, paginar

router = APIRouter(tags=["Avisos WhatsApp"])
LECTURA = requiere("operacion", "lectura")
ESCRITURA = requiere("operacion", "escritura")


class MensajeOut(BaseModel):
    id_mensaje: int
    id_alerta: int | None
    paciente: str
    destinatario: str
    telefono: str | None  # enmascarado
    tipo_mensaje: str
    contenido: str
    estado: str
    motivo: str | None
    intentos: int
    proximo_intento: datetime | None
    fecha_creacion: datetime
    fecha_envio: datetime | None
    fecha_entrega: datetime | None
    fecha_lectura: datetime | None


class ResumenOut(BaseModel):
    modo: Literal["simulado", "meta"]
    activo: bool
    plantilla: str
    minutos_entre_avisos: int
    planes_con_whatsapp: list[str]
    familiares_habilitados: int
    familiares_total: int
    ultimas_24h: dict[str, int]
    ultimos_7d: dict[str, int]
    entrega_seg_prom: float | None  # de la alerta al «entregado»


class EventoSaludIn(BaseModel):
    id_paciente: int
    tipo: Literal["vital", "caida", "sos"]
    signo_vital: str | None = Field(None, max_length=40)
    valor: float | None = None

    @model_validator(mode="after")
    def _vital(self):
        if self.tipo == "vital" and (not self.signo_vital or self.valor is None):
            raise ValueError("Una lectura de signo vital necesita signo_vital y valor.")
        return self


class EventoSaludOut(BaseModel):
    nivel: str | None
    id_alerta: int | None
    severidad: str | None
    avisos: list[MensajeOut]
    mensaje: str


class PacienteOpcion(BaseModel):
    id_paciente: int
    nombre: str
    plan: str | None
    con_whatsapp: bool
    familiares_habilitados: int


class SignoOpcion(BaseModel):
    signo_vital: str
    nombre: str
    unidad: str
    verde_min: float
    verde_max: float
    amarillo_min: float
    amarillo_max: float


class OpcionesOut(BaseModel):
    pacientes: list[PacienteOpcion]
    signos: list[SignoOpcion]


def mensaje_out(m: MensajeWhatsapp) -> MensajeOut:
    return MensajeOut(id_mensaje=m.id_mensaje, id_alerta=m.id_alerta, paciente=m.paciente.nombre,
                      destinatario=m.destinatario.nombre, telefono=wa.enmascarar(m.telefono),
                      tipo_mensaje=m.tipo_mensaje, contenido=m.contenido, estado=m.estado, motivo=m.motivo,
                      intentos=m.intentos, proximo_intento=m.proximo_intento, fecha_creacion=m.fecha_creacion,
                      fecha_envio=m.fecha_envio, fecha_entrega=m.fecha_entrega, fecha_lectura=m.fecha_lectura)


def _enviar_en_segundo_plano() -> None:
    with SessionLocal() as db:
        wa.procesar_pendientes(db)


def _conteo(db: Session, desde: datetime) -> dict[str, int]:
    filas = db.execute(select(MensajeWhatsapp.estado, func.count()).where(MensajeWhatsapp.fecha_creacion >= desde)
                       .group_by(MensajeWhatsapp.estado)).all()
    base = {e: 0 for e in ("pendiente", "enviado", "entregado", "leido", "fallido", "omitido")}
    base.update({e: n for e, n in filas})
    return base


# ---------------------------------------------------------------- consola
@router.get("/whatsapp/resumen", response_model=ResumenOut, summary="CU43 · Configuración e indicadores de los avisos")
def resumen(_: MiembroStaff = Depends(LECTURA), db: Session = Depends(get_db)):
    st = get_settings()
    ahora = utcnow()
    planes = db.scalars(select(Plan.nombre).join(PlanFuncionalidad, PlanFuncionalidad.codigo_plan == Plan.codigo_plan)
                        .where(PlanFuncionalidad.codigo_funcionalidad == wa.FUNCIONALIDAD).order_by(Plan.orden)).all()
    familiares = select(MembresiaCirculo.id_usuario).where(MembresiaCirculo.rol_en_circulo == "familiar",
                                                           MembresiaCirculo.estado == "activo")
    total = db.scalar(select(func.count()).select_from(UsuarioApp).where(UsuarioApp.id_usuario.in_(familiares)))
    hab = db.scalar(select(func.count()).select_from(UsuarioApp).where(
        UsuarioApp.id_usuario.in_(familiares), UsuarioApp.whatsapp_habilitado.is_(True), UsuarioApp.telefono.is_not(None)))
    entregados = db.scalars(select(MensajeWhatsapp).where(MensajeWhatsapp.fecha_entrega.is_not(None),
                                                          MensajeWhatsapp.fecha_creacion >= ahora - timedelta(days=7))).all()
    tiempos = [(m.fecha_entrega - (m.alerta.fecha_emision if m.alerta else m.fecha_creacion)).total_seconds()
               for m in entregados]
    return ResumenOut(modo="meta" if st.whatsapp_modo == "meta" else "simulado", activo=wa.activo(db),
                      plantilla=st.whatsapp_plantilla, minutos_entre_avisos=wa._num(db, "whatsapp_minutos_entre_avisos", 30),
                      planes_con_whatsapp=list(planes), familiares_habilitados=hab or 0, familiares_total=total or 0,
                      ultimas_24h=_conteo(db, ahora - timedelta(hours=24)), ultimos_7d=_conteo(db, ahora - timedelta(days=7)),
                      entrega_seg_prom=round(sum(tiempos) / len(tiempos), 1) if tiempos else None)


@router.get("/whatsapp/opciones", response_model=OpcionesOut, summary="Pacientes y signos vitales para simular un evento")
def opciones(_: MiembroStaff = Depends(LECTURA), db: Session = Depends(get_db)):
    from ..models import UmbralAlerta
    pacientes = []
    for p in db.scalars(select(Paciente).where(Paciente.estado == "activo").order_by(Paciente.nombre)):
        plan = wa.plan_del_paciente(db, p.id_paciente)
        hab = db.scalar(select(func.count()).select_from(UsuarioApp).join(MembresiaCirculo).where(
            MembresiaCirculo.id_paciente == p.id_paciente, MembresiaCirculo.rol_en_circulo == "familiar",
            MembresiaCirculo.estado == "activo", UsuarioApp.whatsapp_habilitado.is_(True), UsuarioApp.telefono.is_not(None)))
        nombre_plan = db.get(Plan, plan).nombre if plan else None
        pacientes.append(PacienteOpcion(id_paciente=p.id_paciente, nombre=p.nombre, plan=nombre_plan,
                                        con_whatsapp=wa.plan_incluye_whatsapp(db, plan), familiares_habilitados=hab or 0))
    umbrales = {(u.signo_vital, u.nivel_semaforo): u for u in db.scalars(select(UmbralAlerta))}
    signos = [SignoOpcion(signo_vital=s, nombre=wa.SIGNOS.get(s, s).capitalize(), unidad=umbrales[(s, "verde")].unidad,
                          verde_min=float(umbrales[(s, "verde")].valor_minimo), verde_max=float(umbrales[(s, "verde")].valor_maximo),
                          amarillo_min=float(umbrales[(s, "amarillo")].valor_minimo),
                          amarillo_max=float(umbrales[(s, "amarillo")].valor_maximo))
              for s in sorted({k[0] for k in umbrales}) if (s, "verde") in umbrales and (s, "amarillo") in umbrales]
    return OpcionesOut(pacientes=pacientes, signos=signos)


@router.get("/whatsapp/mensajes", response_model=Page[MensajeOut], summary="CU43 · Bitácora de avisos enviados")
def mensajes(estado: str | None = None, q: str | None = Query(None, max_length=120), dias: int = Query(7, ge=1, le=90),
             page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
             _: MiembroStaff = Depends(LECTURA), db: Session = Depends(get_db)):
    stmt = select(MensajeWhatsapp).where(MensajeWhatsapp.fecha_creacion >= utcnow() - timedelta(days=dias))
    if estado:
        stmt = stmt.where(MensajeWhatsapp.estado == estado)
    if q:
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(or_(MensajeWhatsapp.id_paciente.in_(select(Paciente.id_paciente).where(func.lower(Paciente.nombre).like(like))),
                              MensajeWhatsapp.id_usuario.in_(select(UsuarioApp.id_usuario).where(func.lower(UsuarioApp.nombre).like(like)))))
    return paginar(db, stmt.order_by(MensajeWhatsapp.id_mensaje.desc()), page, page_size, mensaje_out)


@router.post("/whatsapp/mensajes/{id_mensaje}/reintentar", response_model=MensajeOut, summary="Reintentar un aviso fallido")
def reintentar(id_mensaje: int, request: Request, tareas: BackgroundTasks, staff: MiembroStaff = Depends(ESCRITURA),
               db: Session = Depends(get_db)):
    m = obtener(db, MensajeWhatsapp, id_mensaje, "El aviso")
    if m.estado != "fallido":
        raise ApiError(409, "NOT_FAILED", "Solo se pueden reintentar avisos fallidos.")
    u = m.destinatario
    if not (u.whatsapp_habilitado and u.telefono):
        raise ApiError(409, "NO_CONSENT", "El familiar ya no tiene WhatsApp autorizado o no tiene teléfono.")
    m.estado, m.intentos, m.proximo_intento, m.telefono = "pendiente", 0, utcnow(), u.telefono
    registrar(db, actor=staff, accion="whatsapp.reintentar", tipo_entidad="mensaje_whatsapp", id_entidad=m.id_mensaje,
              antes={"estado": "fallido", "motivo": m.motivo}, request=request)
    db.commit()
    tareas.add_task(_enviar_en_segundo_plano)
    return mensaje_out(m)


class PruebaIn(BaseModel):
    id_usuario: int


@router.get("/whatsapp/diagnostico", summary="Comprobar la conexión con Meta (número, token, plantilla, webhook)")
def ver_diagnostico(_: MiembroStaff = Depends(ESCRITURA)):
    return wa.diagnostico()


@router.post("/whatsapp/prueba", response_model=MensajeOut, status_code=201,
             summary="Enviar un WhatsApp de prueba a un familiar con consentimiento")
def enviar_prueba(data: PruebaIn, request: Request, staff: MiembroStaff = Depends(ESCRITURA), db: Session = Depends(get_db)):
    u = obtener(db, UsuarioApp, data.id_usuario, "El usuario")
    if not (u.whatsapp_habilitado and u.telefono):
        raise ApiError(409, "NO_CONSENT", "El familiar no tiene teléfono o no autorizó los avisos por WhatsApp.")
    memb = sorted(u.membresias, key=lambda m: (m.rol_en_circulo != "familiar", m.estado != "activo"))
    if not memb:
        raise ApiError(409, "NO_PATIENT", "El usuario no pertenece a ningún círculo de cuidado.")
    st = get_settings()
    m = MensajeWhatsapp(id_paciente=memb[0].id_paciente, id_usuario=u.id_usuario, telefono=u.telefono, tipo_mensaje="prueba",
                        plantilla=st.whatsapp_plantilla, estado="pendiente", proximo_intento=utcnow(),
                        contenido=wa.texto_aviso([memb[0].paciente.nombre, "mensaje de prueba de la consola, no hay una emergencia",
                                                  wa._hora_local(utcnow())]))
    db.add(m)
    db.flush()
    wa.enviar(db, m)
    if m.estado == "pendiente":  # una prueba no se reintenta sola: se informa el error de inmediato
        m.estado, m.proximo_intento = "fallido", None
    registrar(db, actor=staff, accion="whatsapp.prueba", tipo_entidad="mensaje_whatsapp", id_entidad=m.id_mensaje,
              despues={"destinatario": u.id_usuario, "telefono": wa.enmascarar(u.telefono), "estado": m.estado,
                       "modo": st.whatsapp_modo}, request=request)
    db.commit()
    return mensaje_out(m)


def _registrar(db: Session, data: EventoSaludIn) -> EventoSaludOut:
    if db.get(Paciente, data.id_paciente) is None:
        raise ApiError(404, "NOT_FOUND", "El paciente no existe.")
    try:
        alerta, nivel, avisos = wa.registrar_evento(db, data.id_paciente, data.tipo, data.signo_vital, data.valor)
    except ValueError as e:
        raise ApiError(422, "UNKNOWN_VITAL_SIGN", str(e)) from None
    if alerta is None:
        texto = "Lectura dentro del rango verde: no se genera alerta."
    elif not avisos:
        texto = ("Alerta registrada (nivel amarillo): no se avisa por WhatsApp." if nivel == "amarillo"
                 else "Alerta crítica registrada: los avisos por WhatsApp están desactivados o el paciente no tiene familiares.")
    else:
        n = sum(a.estado == "pendiente" for a in avisos)
        texto = f"Alerta crítica registrada: {n} aviso(s) por WhatsApp en envío, {len(avisos) - n} omitido(s)."
    return EventoSaludOut(nivel=nivel, id_alerta=alerta.id_alerta if alerta else None,
                          severidad=alerta.severidad if alerta else None, avisos=[mensaje_out(a) for a in avisos], mensaje=texto)


@router.post("/operacion/eventos-salud", response_model=EventoSaludOut, status_code=201,
             summary="CU41 · Simular un evento de salud desde la consola (demo)")
def simular_evento(data: EventoSaludIn, request: Request, tareas: BackgroundTasks,
                   staff: MiembroStaff = Depends(ESCRITURA), db: Session = Depends(get_db)):
    out = _registrar(db, data)
    registrar(db, actor=staff, accion="alerta.simular_evento", tipo_entidad="alerta", id_entidad=out.id_alerta,
              despues=data.model_dump(), request=request)
    db.commit()
    tareas.add_task(_enviar_en_segundo_plano)
    return out


@router.post("/integracion/eventos-salud", response_model=EventoSaludOut, status_code=201,
             summary="CU41 · La Plataforma AgeCare informa un evento de salud (clave X-API-Key)")
def evento_plataforma(data: EventoSaludIn, tareas: BackgroundTasks, x_api_key: str | None = Header(None),
                      db: Session = Depends(get_db)):
    import hmac
    clave = get_settings().plataforma_api_key
    if not clave:
        raise ApiError(503, "INTEGRATION_DISABLED", "La integración con la Plataforma AgeCare no está configurada.")
    if not x_api_key or not hmac.compare_digest(x_api_key, clave):
        raise ApiError(401, "INVALID_API_KEY", "Clave de integración inválida.")
    out = _registrar(db, data)
    db.commit()
    tareas.add_task(_enviar_en_segundo_plano)
    return out


# ---------------------------------------------------------------- webhook de Meta
@router.get("/whatsapp/webhook", include_in_schema=False)
def verificar_webhook(hub_mode: str | None = Query(None, alias="hub.mode"),
                      hub_token: str | None = Query(None, alias="hub.verify_token"),
                      hub_challenge: str | None = Query(None, alias="hub.challenge")):
    import hmac
    esperado = get_settings().whatsapp_verify_token
    if hub_mode == "subscribe" and esperado and hub_token and hmac.compare_digest(hub_token, esperado):
        return Response(content=hub_challenge or "", media_type="text/plain")
    raise ApiError(403, "FORBIDDEN", "Token de verificación inválido.")


@router.post("/whatsapp/webhook", summary="CU42 · Meta informa entregas y lecturas (firma X-Hub-Signature-256)")
async def webhook(request: Request, x_hub_signature_256: str | None = Header(None)):
    cuerpo = await request.body()
    if not wa.firma_valida(cuerpo, x_hub_signature_256):
        raise ApiError(401, "INVALID_SIGNATURE", "Firma del webhook inválida.")
    try:
        payload = json.loads(cuerpo)
    except ValueError:
        raise ApiError(422, "INVALID_JSON", "Cuerpo inválido.") from None
    with SessionLocal() as db:
        cambios = wa.aplicar_estados(db, payload)
    return {"recibido": True, "cambios": cambios}

