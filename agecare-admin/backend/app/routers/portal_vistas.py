"""Portal web · vistas del representante, el residente y el cuidador.

Representante: CU47 Contratar y pagar un plan (Webpay Plus) · CU48 Registrar residente · CU49 Cambiar o cancelar el
plan · CU50 Consultar el estado vital en tiempo real (Platino y Proveedor) · avisos de riesgo dentro del portal.
Residente: CU51 Ver chistes, noticias y eventos · CU52 Pedir ayuda (ticket).
Cuidador: CU53 Registrar el estado vital del residente (Normal / Alerta / Riesgoso).
"""
from datetime import date, datetime, timedelta
from typing import Literal
from urllib.parse import parse_qs

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .. import portal, rut as rutmod, webpay
from ..audit import registrar
from ..config import get_settings
from ..db import get_db, utcnow
from ..errors import ApiError
from ..models import (Contenido, CuentaCliente, MembresiaCirculo, NotificacionApp, OrdenPago, Paciente, ParametroSistema,
                      Plan, RegistroVital, Suscripcion, Ticket, UsuarioApp, UsuarioPerfil)
from ..security import hash_password
from .portal import ClavesIn, _nombre, _ocupado, _rut, vista

router = APIRouter(prefix="/portal", tags=["Portal · vistas"])
REPRESENTANTE, RESIDENTE, CUIDADOR, CUALQUIERA = vista("representante"), vista("residente"), vista("cuidador"), vista()


# ================================================================ esquemas comunes
class PlanPortalOut(BaseModel):
    codigo_plan: str
    nombre: str
    precio: int
    funcionalidades: list[str]
    incluye_estado_tiempo_real: bool
    incluye_avisos_riesgo: bool


class RegistroVitalOut(BaseModel):
    id_registro: int
    estado: str
    etiqueta: str
    observacion: str
    cuidador: str
    fecha: datetime


class ResidenteOut(BaseModel):
    id_paciente: int
    nombre: str
    rut: str | None
    edad: int | None
    email: str | None


class ItemResidenteOut(BaseModel):
    id_suscripcion: int | None
    plan: PlanPortalOut | None
    estado_suscripcion: str | None
    fin_periodo: datetime | None
    puede_gestionar: bool
    residente: ResidenteOut | None
    puede_ver_estado: bool
    recibe_avisos: bool
    ultimo_estado: RegistroVitalOut | None


class NotificacionOut(BaseModel):
    id_notificacion: int
    tipo: str
    titulo: str
    cuerpo: str
    id_paciente: int | None
    fecha_creacion: datetime
    leida: bool
    enlace: str | None = None


class NotificacionesOut(BaseModel):
    sin_leer: int
    items: list[NotificacionOut]


def plan_portal(db: Session, p: Plan) -> PlanPortalOut:
    from ..models import Funcionalidad
    nombres = {f.codigo_funcionalidad: f.nombre for f in db.scalars(select(Funcionalidad))}
    codigos = sorted((f.codigo_funcionalidad for f in p.funcionalidades), key=lambda c: c)
    return PlanPortalOut(codigo_plan=p.codigo_plan, nombre=p.nombre, precio=p.precio,
                         funcionalidades=[nombres.get(c, c) for c in codigos],
                         incluye_estado_tiempo_real=portal.F_ESTADO in codigos, incluye_avisos_riesgo=portal.F_AVISOS in codigos)


def residente_out(db: Session, p: Paciente) -> ResidenteOut:
    email = db.scalar(select(UsuarioApp.email).where(UsuarioApp.id_usuario == p.id_usuario)) if p.id_usuario else None
    return ResidenteOut(id_paciente=p.id_paciente, nombre=p.nombre, rut=rutmod.formatear(p.rut),
                        edad=portal.edad(p.fecha_nacimiento), email=email)


@router.get("/planes", response_model=list[PlanPortalOut], summary="Planes disponibles para contratar")
def planes(_: UsuarioApp = Depends(CUALQUIERA), db: Session = Depends(get_db)):
    return [plan_portal(db, p) for p in db.scalars(select(Plan).where(Plan.activo.is_(True)).order_by(Plan.orden))]


# ================================================================ representante
def _sus_propia(db: Session, u: UsuarioApp, id_suscripcion: int) -> Suscripcion:
    s = db.get(Suscripcion, id_suscripcion)
    if s is None or s.cuenta.id_usuario != u.id_usuario:
        raise ApiError(404, "NOT_FOUND", "La suscripción no existe.")
    return s


def _es_representante_de(db: Session, u: UsuarioApp, id_paciente: int) -> Paciente:
    m = db.get(MembresiaCirculo, (u.id_usuario, id_paciente))
    if m is None or m.rol_en_circulo != "familiar" or m.estado != "activo":
        raise ApiError(404, "NOT_FOUND", "El residente no existe o no está a tu cargo.")
    return m.paciente


@router.get("/representante/residentes", response_model=list[ItemResidenteOut],
            summary="Mis residentes con su plan y su último estado")
def mis_residentes(u: UsuarioApp = Depends(REPRESENTANTE), db: Session = Depends(get_db)):
    subs = db.scalars(select(Suscripcion).join(CuentaCliente).where(CuentaCliente.id_usuario == u.id_usuario)
                      .order_by(Suscripcion.fecha_inicio)).all()
    # Una suscripción cancelada se oculta si el residente ya tiene otra más reciente
    ultima = {}
    for s in subs:
        if s.id_paciente:
            ultima[s.id_paciente] = s.id_suscripcion
    items, vistos = [], set()

    def item(s: Suscripcion | None, p: Paciente | None) -> ItemResidenteOut:
        codigo = (s.codigo_plan if s and s.estado in portal.VIGENTES else None) if s else \
            portal.plan_vigente(db, p.id_paciente)
        ver = p is not None and portal.plan_incluye(db, codigo, portal.F_ESTADO)
        ult = portal.ultimo_registro(db, p.id_paciente) if ver else None
        return ItemResidenteOut(
            id_suscripcion=s.id_suscripcion if s else None, plan=plan_portal(db, s.plan) if s else (
                plan_portal(db, db.get(Plan, codigo)) if codigo else None),
            estado_suscripcion=s.estado if s else ("activa" if codigo else None), fin_periodo=s.fin_periodo if s else None,
            puede_gestionar=s is not None, residente=residente_out(db, p) if p else None, puede_ver_estado=ver,
            recibe_avisos=p is not None and portal.plan_incluye(db, codigo, portal.F_AVISOS),
            ultimo_estado=RegistroVitalOut(**portal.registro_out(ult)) if ult else None)

    for s in subs:
        if s.id_paciente and ultima[s.id_paciente] != s.id_suscripcion:
            continue
        if s.id_paciente is None and s.estado not in portal.VIGENTES:
            continue  # cupo cancelado sin residente
        if s.id_paciente:
            vistos.add(s.id_paciente)
        items.append(item(s, s.paciente))
    for m in u.membresias:  # residentes asignados por soporte con un plan de otra cuenta
        if m.rol_en_circulo == "familiar" and m.estado == "activo" and m.id_paciente not in vistos:
            items.append(item(None, m.paciente))
    return items


class PagoIn(BaseModel):
    tipo: Literal["alta", "renovacion", "cambio"]
    codigo_plan: str = Field(max_length=40)
    id_suscripcion: int | None = None
    id_paciente: int | None = Field(None, description="Alta para un residente que ya existe (plan cancelado)")


class PagoOut(BaseModel):
    resultado: Literal["redirigir", "listo"]
    modo: str
    orden_compra: str | None
    url: str | None
    token: str | None
    id_suscripcion: int | None
    mensaje: str


@router.post("/representante/pagos", response_model=PagoOut, status_code=201,
             summary="CU47/CU49 · Contratar, renovar o cambiar un plan (inicia el pago en la pasarela)")
def iniciar_pago(data: PagoIn, request: Request, u: UsuarioApp = Depends(REPRESENTANTE), db: Session = Depends(get_db)):
    plan = portal.plan_activo(db, data.codigo_plan)
    if plan is None:
        raise ApiError(404, "PLAN_NOT_FOUND", "El plan no existe o no está disponible.")
    s = None
    if data.tipo == "alta":
        if data.id_paciente:
            _es_representante_de(db, u, data.id_paciente)
            actual = portal.suscripcion_de(db, data.id_paciente)
            if actual and actual.estado in portal.VIGENTES:
                raise ApiError(409, "ALREADY_SUBSCRIBED", "Ese residente ya tiene un plan vigente: usa «Cambiar plan».")
    else:
        if not data.id_suscripcion:
            raise ApiError(422, "VALIDATION_ERROR", "Indica la suscripción.", [{"field": "id_suscripcion", "message": "Obligatorio"}])
        s = _sus_propia(db, u, data.id_suscripcion)
        if s.estado not in portal.VIGENTES:
            raise ApiError(409, "SUBSCRIPTION_CLOSED", "Ese plan está cancelado. Contrata uno nuevo para el residente.")
        if data.tipo == "renovacion" and data.codigo_plan != s.codigo_plan:
            raise ApiError(422, "VALIDATION_ERROR", "La renovación es del mismo plan.")
        if data.tipo == "cambio" and data.codigo_plan == s.codigo_plan:
            raise ApiError(409, "NO_CHANGE", "El residente ya tiene ese plan.")

    if plan.precio == 0:  # el plan gratuito no pasa por la pasarela
        if data.tipo == "renovacion":
            raise ApiError(409, "FREE_PLAN", "El plan gratuito no se paga.")
        if s is None:
            s = portal.nueva_suscripcion(db, portal.cuenta_familia(db, u), plan.codigo_plan, data.id_paciente)
        else:
            s.codigo_plan, s.estado = plan.codigo_plan, "activa"
        registrar(db, actor=None, accion=f"portal.plan_{data.tipo}", tipo_entidad="suscripcion", id_entidad=s.id_suscripcion,
                  despues={"plan": plan.codigo_plan, "usuario": u.id_usuario}, request=request)
        db.commit()
        return PagoOut(resultado="listo", modo="gratuito", orden_compra=None, url=None, token=None,
                       id_suscripcion=s.id_suscripcion, mensaje=f"Plan {plan.nombre} activado sin costo.")

    o = OrdenPago(orden_compra=portal.nueva_orden_compra(), id_usuario=u.id_usuario, id_suscripcion=s.id_suscripcion if s else None,
                  id_paciente=data.id_paciente, codigo_plan=plan.codigo_plan, tipo=data.tipo, monto=plan.precio,
                  proveedor=webpay.modo())
    db.add(o)
    db.flush()
    if o.proveedor == "webpay":
        st = get_settings()
        retorno = f"{(st.api_public_url or st.frontend_url).rstrip('/')}/api/v1/portal/pagos/webpay/retorno"
        try:
            r = webpay.crear(o.orden_compra, f"u{u.id_usuario}", o.monto, retorno)
        except webpay.ErrorWebpay as e:
            o.estado, o.detalle = "error", str(e)[:300]
            db.commit()
            raise ApiError(502, "GATEWAY_ERROR", f"No se pudo iniciar el pago en Webpay. {e}")
        o.token, url = r["token"], r["url"]
    else:
        url = f"/portal/pago/simulado?orden={o.orden_compra}"
    registrar(db, actor=None, accion="portal.pago_iniciado", tipo_entidad="orden_pago", id_entidad=o.orden_compra,
              despues={"tipo": o.tipo, "plan": o.codigo_plan, "monto": o.monto, "proveedor": o.proveedor}, request=request)
    db.commit()
    return PagoOut(resultado="redirigir", modo=o.proveedor, orden_compra=o.orden_compra, url=url, token=o.token,
                   id_suscripcion=o.id_suscripcion, mensaje="Te llevamos a la pasarela de pago.")


class ResidenteIn(ClavesIn):
    rut: str = Field(max_length=14)
    primer_nombre: str = Field(min_length=2, max_length=60)
    primer_apellido: str = Field(min_length=2, max_length=60)
    segundo_apellido: str | None = Field(None, max_length=60)
    email: EmailStr
    fecha_nacimiento: date

    @field_validator("rut")
    @classmethod
    def _v_rut(cls, v):
        return _rut(v)

    @field_validator("primer_nombre", "primer_apellido")
    @classmethod
    def _v_nom(cls, v):
        return _nombre(v)

    @field_validator("segundo_apellido")
    @classmethod
    def _v_seg(cls, v):
        return _nombre(v, False)

    @field_validator("fecha_nacimiento")
    @classmethod
    def _v_nac(cls, v: date):
        if v >= date.today() or v.year < 1900:
            raise ValueError("Fecha de nacimiento inválida.")
        return v


def crear_residente(db: Session, datos: "ResidenteIn | object", password_hash: str, debe_cambiar: bool,
                    origen: str) -> Paciente:
    """Crea la cuenta del residente (perfil adulto_mayor) y su ficha (paciente). Lo usan el portal y la consola."""
    r = datos.rut
    _ocupado(db, r, datos.email)
    if db.scalar(select(Paciente.id_paciente).where(Paciente.rut == r)):
        raise ApiError(409, "RUT_EXISTS", "Ya existe un residente con ese RUT.", [{"field": "rut", "message": "RUT ya registrado"}])
    nombre = portal.nombre_completo(datos.primer_nombre, datos.primer_apellido, datos.segundo_apellido)
    cuenta = UsuarioApp(nombre=nombre, nombres=datos.primer_nombre, primer_apellido=datos.primer_apellido,
                        segundo_apellido=datos.segundo_apellido, email=datos.email.lower(), rut=r,
                        password_hash=password_hash, debe_cambiar_password=debe_cambiar, origen=origen)
    db.add(cuenta)
    db.flush()
    db.add(UsuarioPerfil(id_usuario=cuenta.id_usuario, codigo_perfil="adulto_mayor"))
    p = Paciente(nombre=nombre, rut=r, primer_nombre=datos.primer_nombre, primer_apellido=datos.primer_apellido,
                 segundo_apellido=datos.segundo_apellido, fecha_nacimiento=datos.fecha_nacimiento, id_usuario=cuenta.id_usuario)
    db.add(p)
    db.flush()
    return p


@router.post("/representante/suscripciones/{id_suscripcion}/residente", response_model=ItemResidenteOut, status_code=201,
             summary="CU48 · Registrar al residente del plan pagado")
def registrar_residente(id_suscripcion: int, data: ResidenteIn, request: Request,
                        u: UsuarioApp = Depends(REPRESENTANTE), db: Session = Depends(get_db)):
    s = _sus_propia(db, u, id_suscripcion)
    if s.estado != "activa":
        raise ApiError(409, "PAYMENT_REQUIRED", "El plan debe estar pagado y activo para registrar al residente.")
    if s.id_paciente:
        raise ApiError(409, "ALREADY_ASSIGNED", "Este plan ya tiene un residente registrado.")
    p = crear_residente(db, data, hash_password(data.password), False, "portal")
    s.id_paciente = p.id_paciente
    now = utcnow()
    db.add(MembresiaCirculo(id_usuario=u.id_usuario, id_paciente=p.id_paciente, rol_en_circulo="familiar", estado="activo",
                            fecha_invitacion=now, fecha_aceptacion=now))
    registrar(db, actor=None, accion="portal.registrar_residente", tipo_entidad="paciente", id_entidad=p.id_paciente,
              despues={"residente": p.nombre, "representante": u.id_usuario, "suscripcion": s.id_suscripcion}, request=request)
    db.commit()
    db.expire_all()  # la sesión no expira al confirmar: se recargan las relaciones (s.paciente)
    return next(i for i in mis_residentes(u, db) if i.id_suscripcion == s.id_suscripcion)


class CancelarIn(BaseModel):
    motivo: str = Field(min_length=5, max_length=300)


@router.post("/representante/suscripciones/{id_suscripcion}/cancelar", response_model=ItemResidenteOut,
             summary="CU49 · Cancelar el plan de un residente")
def cancelar_plan(id_suscripcion: int, data: CancelarIn, request: Request, u: UsuarioApp = Depends(REPRESENTANTE),
                  db: Session = Depends(get_db)):
    from .. import pasarela
    s = _sus_propia(db, u, id_suscripcion)
    if s.estado not in portal.VIGENTES:
        raise ApiError(409, "SUBSCRIPTION_CLOSED", "El plan ya está cancelado.")
    pasarela.cancelar_suscripcion(s.id_externo_pasarela)
    s.estado, s.fecha_cancelacion, s.motivo_cancelacion = "cancelada", utcnow(), data.motivo.strip()
    registrar(db, actor=None, accion="portal.cancelar_plan", tipo_entidad="suscripcion", id_entidad=s.id_suscripcion,
              despues={"motivo": s.motivo_cancelacion, "usuario": u.id_usuario}, request=request)
    portal.notificar(db, u.id_usuario, "plan", "Plan cancelado",
                     f"Cancelaste el plan {s.plan.nombre}" + (f" de {s.paciente.nombre}." if s.paciente else "."), s.id_paciente)
    db.commit()
    return ItemResidenteOut(id_suscripcion=s.id_suscripcion, plan=plan_portal(db, s.plan), estado_suscripcion=s.estado,
                            fin_periodo=s.fin_periodo, puede_gestionar=True,
                            residente=residente_out(db, s.paciente) if s.paciente else None, puede_ver_estado=False,
                            recibe_avisos=False, ultimo_estado=None)


class EstadoVitalOut(BaseModel):
    residente: ResidenteOut
    plan: str | None
    actual: RegistroVitalOut | None
    historial: list[RegistroVitalOut]
    consultado: datetime
    actualizar_cada_seg: int


@router.get("/representante/residentes/{id_paciente}/estado", response_model=EstadoVitalOut,
            summary="CU50 · Estado vital en tiempo real (planes Platino y Proveedor)")
def estado_residente(id_paciente: int, u: UsuarioApp = Depends(REPRESENTANTE), db: Session = Depends(get_db)):
    p = _es_representante_de(db, u, id_paciente)
    codigo = portal.plan_vigente(db, id_paciente)
    if not portal.plan_incluye(db, codigo, portal.F_ESTADO):
        nombre = db.get(Plan, codigo).nombre if codigo else "sin plan vigente"
        raise ApiError(403, "PLAN_REQUIRED", f"El plan actual ({nombre}) no incluye el estado en tiempo real. "
                       "Está disponible en los planes Platino y Proveedor.")
    regs = db.scalars(select(RegistroVital).where(RegistroVital.id_paciente == id_paciente)
                      .order_by(RegistroVital.fecha.desc(), RegistroVital.id_registro.desc()).limit(10)).all()
    return EstadoVitalOut(residente=residente_out(db, p), plan=codigo,
                          actual=RegistroVitalOut(**portal.registro_out(regs[0])) if regs else None,
                          historial=[RegistroVitalOut(**portal.registro_out(r)) for r in regs], consultado=utcnow(),
                          actualizar_cada_seg=15)


# ================================================================ pagos (retorno de la pasarela)
class OrdenOut(BaseModel):
    orden_compra: str
    estado: str
    tipo: str
    plan: str
    monto: int
    proveedor: str
    fecha_creacion: datetime
    fecha_confirmacion: datetime | None
    codigo_autorizacion: str | None
    tarjeta: str | None
    tipo_pago: str | None
    detalle: str | None
    id_suscripcion: int | None
    requiere_residente: bool


def orden_out(db: Session, o: OrdenPago) -> OrdenOut:
    s = db.get(Suscripcion, o.id_suscripcion) if o.id_suscripcion else None
    return OrdenOut(orden_compra=o.orden_compra, estado=o.estado, tipo=o.tipo, plan=o.plan.nombre, monto=o.monto,
                    proveedor=o.proveedor, fecha_creacion=o.fecha_creacion, fecha_confirmacion=o.fecha_confirmacion,
                    codigo_autorizacion=o.codigo_autorizacion, tarjeta=o.tarjeta,
                    tipo_pago=webpay.TIPOS_PAGO.get(o.tipo_pago or "", o.tipo_pago), detalle=o.detalle,
                    id_suscripcion=o.id_suscripcion,
                    requiere_residente=o.estado == "aprobada" and s is not None and s.id_paciente is None)


def _resultado(o_compra: str | None) -> RedirectResponse:
    st = get_settings()
    destino = f"{st.frontend_url.rstrip('/')}/portal/pago/resultado" + (f"?orden={o_compra}" if o_compra else "")
    return RedirectResponse(destino, status_code=303)


@router.api_route("/pagos/webpay/retorno", methods=["GET", "POST"], include_in_schema=True,
                  summary="Retorno desde Webpay (confirma el pago y redirige al portal)")
async def retorno_webpay(request: Request, db: Session = Depends(get_db)):
    """Webpay vuelve con token_ws (pagado o rechazado), TBK_TOKEN (el usuario anuló) o solo TBK_ORDEN_COMPRA
    (tiempo agotado). En integración la anulación llega por POST; el resto por GET."""
    campos = {k: v[0] for k, v in parse_qs((await request.body()).decode(errors="ignore")).items()} \
        if request.method == "POST" else {}
    campos.update(request.query_params)
    token, tbk_token, orden_c = campos.get("token_ws"), campos.get("TBK_TOKEN"), campos.get("TBK_ORDEN_COMPRA")
    o = None
    if tbk_token or (orden_c and not token):
        o = db.scalar(select(OrdenPago).where(OrdenPago.orden_compra == (orden_c or "")[:26]))
        if o is None and tbk_token:
            o = db.scalar(select(OrdenPago).where(OrdenPago.token == tbk_token[:100]))
        if o and o.estado == "iniciada":
            o.estado, o.fecha_confirmacion = "anulada", utcnow()
            o.detalle = "Pago anulado en Webpay." if tbk_token else "Se agotó el tiempo para pagar en Webpay."
            db.commit()
        return _resultado(o.orden_compra if o else None)
    if not token:
        return _resultado(None)
    o = db.scalar(select(OrdenPago).where(OrdenPago.token == token[:100]))
    if o is None:
        return _resultado(None)
    if o.estado == "iniciada":  # una recarga de la página no vuelve a confirmar
        try:
            r = webpay.confirmar(token)
        except webpay.ErrorWebpay as e:
            o.estado, o.detalle, o.fecha_confirmacion = "error", str(e)[:300], utcnow()
            db.commit()
            return _resultado(o.orden_compra)
        ok = webpay.aprobado(r) and r.get("buy_order") == o.orden_compra and int(r.get("amount", -1)) == o.monto
        portal.aplicar_pago(db, o, ok, autorizacion=r.get("authorization_code"),
                            tarjeta=(r.get("card_detail") or {}).get("card_number"), tipo_pago=r.get("payment_type_code"),
                            codigo_respuesta=r.get("response_code"),
                            detalle=None if ok else "Webpay rechazó el pago (tarjeta o fondos).",
                            proveedor_ref=f"wp_{o.orden_compra}_{r.get('authorization_code') or 'x'}")
        registrar(db, actor=None, accion="portal.pago_webpay", tipo_entidad="orden_pago", id_entidad=o.orden_compra,
                  despues={"estado": o.estado, "response_code": r.get("response_code"), "status": r.get("status")},
                  request=request)
        db.commit()
    return _resultado(o.orden_compra)


@router.get("/pagos/{orden_compra}", response_model=OrdenOut, summary="Resultado de un pago (comprobante)")
def ver_orden(orden_compra: str, db: Session = Depends(get_db)):
    """Sin sesión: Webpay vuelve al portal desde otro sitio. El número de orden es aleatorio y no se puede adivinar."""
    o = db.scalar(select(OrdenPago).where(OrdenPago.orden_compra == orden_compra[:26]))
    if o is None:
        raise ApiError(404, "NOT_FOUND", "La orden de pago no existe.")
    return orden_out(db, o)


class SimuladoIn(BaseModel):
    aprobar: bool


@router.post("/pagos/{orden_compra}/simulado", response_model=OrdenOut,
             summary="Pasarela simulada: aprobar o rechazar el pago (solo PAGOS_MODO=simulado)")
def pagar_simulado(orden_compra: str, data: SimuladoIn, request: Request, u: UsuarioApp = Depends(REPRESENTANTE),
                   db: Session = Depends(get_db)):
    o = db.scalar(select(OrdenPago).where(OrdenPago.orden_compra == orden_compra[:26]))
    if o is None or o.id_usuario != u.id_usuario:
        raise ApiError(404, "NOT_FOUND", "La orden de pago no existe.")
    if o.proveedor != "simulado":
        raise ApiError(409, "NOT_SIMULATED", "Esta orden se paga en Webpay.")
    portal.aplicar_pago(db, o, data.aprobar, autorizacion=f"{utcnow():%H%M%S}" if data.aprobar else None, tarjeta="4242",
                        tipo_pago="VN", codigo_respuesta=0 if data.aprobar else -1,
                        detalle=None if data.aprobar else "Pago rechazado en la pasarela simulada.")
    registrar(db, actor=None, accion="portal.pago_simulado", tipo_entidad="orden_pago", id_entidad=o.orden_compra,
              despues={"estado": o.estado}, request=request)
    db.commit()
    return orden_out(db, o)


# ================================================================ avisos dentro del portal
@router.get("/notificaciones", response_model=NotificacionesOut, summary="Avisos del portal (campana)")
def notificaciones(u: UsuarioApp = Depends(CUALQUIERA), db: Session = Depends(get_db)):
    rows = db.scalars(select(NotificacionApp).where(NotificacionApp.id_usuario == u.id_usuario)
                      .order_by(NotificacionApp.fecha_creacion.desc(), NotificacionApp.id_notificacion.desc()).limit(30)).all()
    sin_leer = db.scalar(select(func.count()).where(NotificacionApp.id_usuario == u.id_usuario,
                                                    NotificacionApp.fecha_lectura.is_(None)))
    return NotificacionesOut(sin_leer=sin_leer or 0, items=[
        NotificacionOut(id_notificacion=n.id_notificacion, tipo=n.tipo, titulo=n.titulo, cuerpo=n.cuerpo,
                        id_paciente=n.id_paciente, fecha_creacion=n.fecha_creacion, leida=n.fecha_lectura is not None,
                        enlace=n.enlace)
        for n in rows])


@router.post("/notificaciones/leer", response_model=NotificacionesOut, summary="Marcar los avisos como leídos")
def leer_notificaciones(u: UsuarioApp = Depends(CUALQUIERA), db: Session = Depends(get_db)):
    for n in db.scalars(select(NotificacionApp).where(NotificacionApp.id_usuario == u.id_usuario,
                                                      NotificacionApp.fecha_lectura.is_(None))):
        n.fecha_lectura = utcnow()
    db.commit()
    return notificaciones(u, db)


# ================================================================ residente
class ContenidoPortalOut(BaseModel):
    id_contenido: int
    tipo: str
    titulo: str
    cuerpo: str
    fecha_publicacion: datetime | None
    fecha_evento: datetime | None
    lugar: str | None


class InicioResidenteOut(BaseModel):
    nombre: str
    mensaje_bienvenida: str
    representantes: list[str]
    cuidadores: list[str]


@router.get("/residente/inicio", response_model=InicioResidenteOut, summary="CU51 · Inicio del residente")
def inicio_residente(u: UsuarioApp = Depends(RESIDENTE), db: Session = Depends(get_db)):
    p = db.scalar(select(Paciente).where(Paciente.id_usuario == u.id_usuario))
    reps, cuids = [], []
    if p:
        for m in db.scalars(select(MembresiaCirculo).where(MembresiaCirculo.id_paciente == p.id_paciente,
                                                           MembresiaCirculo.estado == "activo")):
            nombre = db.get(UsuarioApp, m.id_usuario).nombre
            (reps if m.rol_en_circulo == "familiar" else cuids if m.rol_en_circulo == "cuidadora" else []).append(nombre)
    msg = db.get(ParametroSistema, "mensaje_bienvenida_app")
    return InicioResidenteOut(nombre=u.nombres or u.nombre, mensaje_bienvenida=msg.valor if msg else "Bienvenido a AgeCare",
                              representantes=reps, cuidadores=cuids)


@router.get("/contenidos", response_model=list[ContenidoPortalOut], summary="CU51 · Chistes, noticias y eventos publicados")
def contenidos(tipo: Literal["chiste", "noticia", "evento"] | None = None, u: UsuarioApp = Depends(CUALQUIERA),
               db: Session = Depends(get_db)):
    from .contenido import publicar_programados
    publicar_programados(db)
    stmt = select(Contenido).where(Contenido.estado == "publicado", Contenido.fecha_eliminacion.is_(None))
    if tipo:
        stmt = stmt.where(Contenido.tipo == tipo)
    # Los eventos pasados (más de un día) dejan de mostrarse; los próximos van primero
    stmt = stmt.where(or_(Contenido.tipo != "evento", Contenido.fecha_evento.is_(None),
                          Contenido.fecha_evento >= utcnow() - timedelta(days=1)))
    rows = db.scalars(stmt.order_by(Contenido.fecha_publicacion.desc()).limit(40)).all()
    if tipo == "evento":
        rows = sorted(rows, key=lambda c: c.fecha_evento or c.fecha_publicacion or utcnow())
    return [ContenidoPortalOut(id_contenido=c.id_contenido, tipo=c.tipo, titulo=c.titulo, cuerpo=c.cuerpo,
                               fecha_publicacion=c.fecha_publicacion, fecha_evento=c.fecha_evento, lugar=c.lugar) for c in rows]


class AyudaIn(BaseModel):
    categoria: Literal["acceso_cuenta", "pagos_planes", "alertas_push", "wearable", "medicamentos", "otros"] = "otros"
    asunto: str = Field(min_length=5, max_length=160)
    descripcion: str = Field(min_length=10, max_length=2000)


class AyudaOut(BaseModel):
    numero: int
    mensaje: str


@router.post("/ayuda", response_model=AyudaOut, status_code=201, summary="CU52 · Pedir ayuda (crea un ticket con canal App)")
def pedir_ayuda(data: AyudaIn, request: Request, u: UsuarioApp = Depends(CUALQUIERA), db: Session = Depends(get_db)):
    abiertos = db.scalar(select(func.count()).where(Ticket.id_usuario == u.id_usuario, Ticket.canal == "app",
                                                    Ticket.fecha_creacion >= utcnow() - timedelta(hours=1)))
    if abiertos >= 5:
        raise ApiError(429, "RATE_LIMITED", "Ya enviaste varias solicitudes en la última hora. Soporte las está revisando.")
    vistas = ", ".join(portal.vistas_de(u))
    t = portal.crear_ticket(db, data.categoria, data.asunto.strip(),
                            f"{data.descripcion.strip()}\n\n— Enviado desde el portal web (vista: {vistas}).", usuario=u)
    registrar(db, actor=None, accion="portal.ayuda", tipo_entidad="ticket", id_entidad=t.numero,
              despues={"categoria": data.categoria, "usuario": u.id_usuario}, request=request)
    db.commit()
    return AyudaOut(numero=t.numero, mensaje=f"Recibimos tu solicitud #{t.numero}. Verás la respuesta de soporte en "
                                             "«Mis solicitudes» y te avisaremos por correo.")


# ================================================================ cuidador
class ResidenteCuidadorOut(BaseModel):
    residente: ResidenteOut
    ultimo_estado: RegistroVitalOut | None


class FichaIn(BaseModel):
    estado: Literal["normal", "alerta", "riesgoso"]
    observacion: str = Field(min_length=3, max_length=1000)


class FichaOut(BaseModel):
    registro: RegistroVitalOut
    avisos_whatsapp: int
    avisos_portal: int
    mensaje: str


def _cuida_a(db: Session, u: UsuarioApp, id_paciente: int) -> Paciente:
    m = db.get(MembresiaCirculo, (u.id_usuario, id_paciente))
    if m is None or m.rol_en_circulo != "cuidadora" or m.estado != "activo":
        raise ApiError(404, "NOT_FOUND", "El residente no existe o no está asignado a ti.")
    return m.paciente


@router.get("/cuidador/residentes", response_model=list[ResidenteCuidadorOut], summary="Residentes asignados al cuidador")
def residentes_cuidador(u: UsuarioApp = Depends(CUIDADOR), db: Session = Depends(get_db)):
    out = []
    for m in sorted(u.membresias, key=lambda m: m.paciente.nombre):
        if m.rol_en_circulo == "cuidadora" and m.estado == "activo":
            ult = portal.ultimo_registro(db, m.id_paciente)
            out.append(ResidenteCuidadorOut(residente=residente_out(db, m.paciente),
                                            ultimo_estado=RegistroVitalOut(**portal.registro_out(ult)) if ult else None))
    return out


@router.post("/cuidador/residentes/{id_paciente}/ficha", response_model=FichaOut, status_code=201,
             summary="CU53 · Registrar el estado vital (Riesgoso avisa por WhatsApp y en el portal según el plan)")
def registrar_ficha(id_paciente: int, data: FichaIn, request: Request, tareas: BackgroundTasks,
                    u: UsuarioApp = Depends(CUIDADOR), db: Session = Depends(get_db)):
    p = _cuida_a(db, u, id_paciente)
    reg, n_wa, n_app = portal.registrar_ficha(db, u, p, data.estado, data.observacion)
    registrar(db, actor=None, accion="portal.ficha_vital", tipo_entidad="registro_vital", id_entidad=reg.id_registro,
              despues={"paciente": id_paciente, "estado": data.estado, "cuidador": u.id_usuario,
                       "avisos_whatsapp": n_wa, "avisos_portal": n_app}, request=request)
    db.commit()
    db.refresh(reg)
    if data.estado == "riesgoso":
        msg = (f"Estado Riesgoso registrado. Se avisó a {n_app} representante(s) en el portal y se enviaron {n_wa} "
               "WhatsApp." if n_app or n_wa else
               "Estado Riesgoso registrado. El plan del residente no incluye avisos automáticos: llama a su representante.")
    else:
        msg = f"Estado {portal.ETIQUETA_ESTADO[data.estado]} registrado."
    if n_wa:
        from .whatsapp import _enviar_en_segundo_plano
        tareas.add_task(_enviar_en_segundo_plano)  # envío inmediato; el planificador reintenta si falla
    return FichaOut(registro=RegistroVitalOut(**portal.registro_out(reg)), avisos_whatsapp=n_wa, avisos_portal=n_app,
                    mensaje=msg)


@router.get("/cuidador/residentes/{id_paciente}/historial", response_model=list[RegistroVitalOut],
            summary="Historial de la ficha vital del residente")
def historial(id_paciente: int, u: UsuarioApp = Depends(CUIDADOR), db: Session = Depends(get_db)):
    _cuida_a(db, u, id_paciente)
    regs = db.scalars(select(RegistroVital).where(RegistroVital.id_paciente == id_paciente)
                      .order_by(RegistroVital.fecha.desc(), RegistroVital.id_registro.desc()).limit(30)).all()
    return [RegistroVitalOut(**portal.registro_out(r)) for r in regs]



# ================================================================ v0.7 · «Mis solicitudes» (CU57)
ESTADO_TICKET = {"abierto": "Recibida", "en_curso": "En atención", "esperando_usuario": "Espera tu respuesta",
                 "resuelto": "Resuelta", "cerrado": "Cerrada"}


class SolicitudOut(BaseModel):
    numero: int
    asunto: str
    categoria: str
    estado: str
    estado_texto: str
    fecha_creacion: datetime
    fecha_actualizacion: datetime
    solicitante: str
    es_mia: bool
    residente: str | None
    respuestas_soporte: int
    encuesta_pendiente: bool


class MensajeOut(BaseModel):
    autor: str
    de_soporte: bool
    cuerpo: str
    fecha: datetime


class EncuestaPortalOut(BaseModel):
    puntaje: int | None
    comentario: str | None
    fecha_respuesta: datetime | None


class SolicitudDetalleOut(SolicitudOut):
    descripcion: str
    conversacion: list[MensajeOut]
    puede_responder: bool
    encuesta: EncuestaPortalOut | None


def _solicitud(db: Session, u: UsuarioApp, t: Ticket) -> dict:
    staff = [r for r in t.respuestas if r.tipo_autor == "staff" and not r.es_interna]
    pendiente = (t.encuesta is not None and t.encuesta.fecha_respuesta is None and t.estado in ("resuelto", "cerrado"))
    return dict(numero=t.numero, asunto=t.asunto, categoria=t.categoria.nombre, estado=t.estado,
                estado_texto=ESTADO_TICKET.get(t.estado, t.estado), fecha_creacion=t.fecha_creacion,
                fecha_actualizacion=t.fecha_actualizacion,
                solicitante=t.usuario.nombre if t.usuario else (t.nombre_solicitante or "—"),
                es_mia=t.id_usuario == u.id_usuario, residente=t.paciente.nombre if t.paciente else None,
                respuestas_soporte=len(staff), encuesta_pendiente=pendiente)


def _ticket_visible(db: Session, u: UsuarioApp, numero: int) -> Ticket:
    t = db.scalar(select(Ticket).where(Ticket.numero == numero))
    if t is None or not portal.puede_ver_ticket(db, u, t):
        raise ApiError(404, "NOT_FOUND", "La solicitud no existe o no es tuya.")
    return t


def _detalle(db: Session, u: UsuarioApp, t: Ticket) -> SolicitudDetalleOut:
    from .soporte import respuesta_out
    conv = [MensajeOut(autor=respuesta_out(r).autor_nombre if r.tipo_autor != "staff"
                       else f"{r.autor.nombre_completo.split()[0] if r.autor else 'Soporte'} · Soporte AgeCare",
                       de_soporte=r.tipo_autor == "staff", cuerpo=r.cuerpo, fecha=r.fecha)
            for r in sorted(t.respuestas, key=lambda r: (r.fecha, r.id_respuesta))
            if not r.es_interna and r.tipo_autor in ("staff", "usuario")]
    e = t.encuesta
    return SolicitudDetalleOut(**_solicitud(db, u, t), descripcion=t.descripcion, conversacion=conv,
                               puede_responder=t.estado != "cerrado",
                               encuesta=EncuestaPortalOut(puntaje=e.puntaje, comentario=e.comentario,
                                                          fecha_respuesta=e.fecha_respuesta) if e else None)


@router.get("/solicitudes", response_model=list[SolicitudOut],
            summary="CU57 · Mis solicitudes (y las de mis residentes, si soy representante)")
def mis_solicitudes(u: UsuarioApp = Depends(CUALQUIERA), db: Session = Depends(get_db)):
    mios = portal.residentes_de(db, u)
    cond = Ticket.id_usuario == u.id_usuario
    if mios:
        cond = or_(cond, Ticket.id_paciente.in_(mios))
    rows = db.scalars(select(Ticket).where(cond).order_by(Ticket.fecha_actualizacion.desc()).limit(50)).unique().all()
    return [SolicitudOut(**_solicitud(db, u, t)) for t in rows]


@router.get("/solicitudes/{numero}", response_model=SolicitudDetalleOut, summary="CU57 · Ver una solicitud y su conversación")
def ver_solicitud(numero: int, u: UsuarioApp = Depends(CUALQUIERA), db: Session = Depends(get_db)):
    return _detalle(db, u, _ticket_visible(db, u, numero))


class ResponderIn(BaseModel):
    cuerpo: str = Field(min_length=2, max_length=2000)


@router.post("/solicitudes/{numero}/respuestas", response_model=SolicitudDetalleOut, status_code=201,
             summary="CU57 · Responder a soporte (reabre la solicitud si estaba resuelta)")
def responder_solicitud(numero: int, data: ResponderIn, request: Request, u: UsuarioApp = Depends(CUALQUIERA),
                        db: Session = Depends(get_db)):
    from ..models import RespuestaTicket
    t = _ticket_visible(db, u, numero)
    if t.estado == "cerrado":
        raise ApiError(409, "TICKET_CLOSED", "Esta solicitud está cerrada. Si necesitas algo más, crea una nueva.")
    now = utcnow()
    db.add(RespuestaTicket(id_ticket=t.id_ticket, tipo_autor="usuario", id_usuario_autor=u.id_usuario,
                           cuerpo=data.cuerpo.strip(), fecha=now))
    anterior = t.estado
    if t.estado in ("resuelto", "esperando_usuario"):
        t.estado = "en_curso"  # vuelve a la cola de soporte
        t.fecha_resolucion = None
    t.fecha_actualizacion = now
    registrar(db, actor=None, accion="portal.responder_ticket", tipo_entidad="ticket", id_entidad=t.id_ticket,
              antes={"estado": anterior}, despues={"estado": t.estado, "usuario": u.id_usuario}, request=request)
    db.commit()
    db.expire_all()
    return _detalle(db, u, _ticket_visible(db, u, numero))


class EncuestaIn(BaseModel):
    puntaje: int = Field(ge=1, le=5)
    comentario: str | None = Field(None, max_length=1000)


@router.post("/solicitudes/{numero}/encuesta", response_model=SolicitudDetalleOut,
             summary="CU40 · Calificar la atención (encuesta de satisfacción)")
def responder_encuesta(numero: int, data: EncuestaIn, request: Request, u: UsuarioApp = Depends(CUALQUIERA),
                       db: Session = Depends(get_db)):
    t = _ticket_visible(db, u, numero)
    e = t.encuesta
    if e is None or t.estado not in ("resuelto", "cerrado"):
        raise ApiError(409, "SURVEY_NOT_AVAILABLE", "La encuesta se habilita cuando soporte resuelve la solicitud.")
    if e.fecha_respuesta is not None:
        raise ApiError(409, "SURVEY_ANSWERED", "Ya calificaste esta atención. ¡Gracias!")
    e.puntaje, e.comentario, e.fecha_respuesta = data.puntaje, (data.comentario or "").strip() or None, utcnow()
    registrar(db, actor=None, accion="portal.encuesta", tipo_entidad="ticket", id_entidad=t.id_ticket,
              despues={"puntaje": data.puntaje, "usuario": u.id_usuario}, request=request)
    db.commit()
    db.expire_all()
    return _detalle(db, u, _ticket_visible(db, u, numero))
