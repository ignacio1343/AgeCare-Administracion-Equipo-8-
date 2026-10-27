"""Planes comerciales y suscripciones: CU09 Gestionar planes · CU10 Gestionar cuentas de clientes
· CU11 Gestionar suscripciones · CU12 Cancelar suscripción · CU13 Consultar transacciones · CU14 Registrar evento de pago
· CU15 Procesar reembolso."""
import json
import re
from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Header, Query, Request
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .. import pasarela
from ..audit import registrar
from ..db import get_db, utcnow
from ..deps import requiere
from ..errors import ApiError
from ..models import (CuentaCliente, EventoPago, Funcionalidad, MiembroStaff, Plan, PlanFuncionalidad, Reembolso,
                      Suscripcion, TransaccionPago, UsuarioApp)
from ..schemas import Page
from ..util import obtener, paginar

router = APIRouter(tags=["Planes y suscripciones"])
LECTURA, ESCRITURA = requiere("comercial", "lectura"), requiere("comercial", "escritura")


# ---------------------------------------------------------------- esquemas
class PlanOut(BaseModel):
    codigo_plan: str
    nombre: str
    precio: int
    moneda: str
    unidad_facturable: str
    periodicidad: str
    activo: bool
    funcionalidades: list[str]
    suscripciones_activas: int


class PlanIn(BaseModel):
    nombre: str | None = Field(None, min_length=3, max_length=120)
    precio: int | None = Field(None, ge=0, le=10_000_000)
    activo: bool | None = None
    funcionalidades: list[str] | None = None


class FuncionalidadOut(BaseModel):
    codigo: str
    nombre: str


class SuscripcionOut(BaseModel):
    id_suscripcion: int
    id_cuenta: int
    cuenta: str
    tipo_cuenta: str
    codigo_plan: str
    plan: str
    precio: int
    estado: str
    fecha_inicio: datetime
    inicio_periodo: datetime
    fin_periodo: datetime
    fecha_cancelacion: datetime | None
    motivo_cancelacion: str | None


class CuentaOut(BaseModel):
    id_cuenta: int
    tipo_cuenta: str
    nombre: str
    email_facturacion: str
    rut: str | None
    estado: str
    titular: str
    titular_email: str
    fecha_creacion: datetime
    suscripcion_actual: SuscripcionOut | None


class ReembolsoOut(BaseModel):
    id_reembolso: int
    monto: int
    motivo: str
    estado: str
    autorizador: str
    fecha: datetime


class TransaccionOut(BaseModel):
    id_transaccion: int
    id_suscripcion: int
    cuenta: str
    plan: str
    monto: int
    moneda: str
    estado: str
    fecha: datetime
    medio_pago: str | None
    codigo_error: str | None
    id_externo_pasarela: str | None
    reembolsado: int
    reembolsable: int
    reembolsos: list[ReembolsoOut]


class CuentaDetalleOut(CuentaOut):
    suscripciones: list[SuscripcionOut]
    transacciones: list[TransaccionOut]


def _rut_valido(rut: str) -> bool:
    r = re.sub(r"[.\-\s]", "", rut).upper()
    if not re.fullmatch(r"\d{7,8}[\dK]", r):
        return False
    cuerpo, dv = r[:-1], r[-1]
    s, m = 0, 2
    for d in reversed(cuerpo):
        s += int(d) * m
        m = 2 if m == 7 else m + 1
    res = 11 - s % 11
    return dv == {11: "0", 10: "K"}.get(res, str(res))


class CuentaIn(BaseModel):
    email_titular: EmailStr
    tipo_cuenta: Literal["familia", "proveedor"]
    nombre: str = Field(min_length=3, max_length=120)
    email_facturacion: EmailStr
    rut: str | None = None
    codigo_plan: str | None = None

    @field_validator("rut")
    @classmethod
    def _rut(cls, v):
        if v and not _rut_valido(v):
            raise ValueError("RUT inválido.")
        return v


class CuentaUpdateIn(BaseModel):
    nombre: str | None = Field(None, min_length=3, max_length=120)
    email_facturacion: EmailStr | None = None
    estado: Literal["activa", "suspendida"] | None = None


class CambioPlanIn(BaseModel):
    codigo_plan: str


class CancelarIn(BaseModel):
    motivo: str = Field(min_length=5, max_length=300)


class ReembolsoIn(BaseModel):
    monto: int = Field(gt=0)
    motivo: str = Field(min_length=5, max_length=300)


class EventoOut(BaseModel):
    id_evento: int
    id_externo_evento: str
    tipo_evento: str
    id_transaccion: int | None
    procesado: bool
    error_procesamiento: str | None
    fecha_recepcion: datetime


class ResumenOut(BaseModel):
    mrr: int
    suscripciones_activas: int
    en_mora: int
    canceladas_30d: int
    ingresos_30d: int
    reembolsos_30d: int
    rechazos_30d: int


# ---------------------------------------------------------------- mapeos
def sus_out(s: Suscripcion) -> SuscripcionOut:
    return SuscripcionOut(id_suscripcion=s.id_suscripcion, id_cuenta=s.id_cuenta, cuenta=s.cuenta.nombre,
                          tipo_cuenta=s.cuenta.tipo_cuenta, codigo_plan=s.codigo_plan, plan=s.plan.nombre,
                          precio=s.plan.precio, estado=s.estado, fecha_inicio=s.fecha_inicio,
                          inicio_periodo=s.inicio_periodo, fin_periodo=s.fin_periodo,
                          fecha_cancelacion=s.fecha_cancelacion, motivo_cancelacion=s.motivo_cancelacion)


def _actual(db: Session, id_cuenta: int) -> Suscripcion | None:
    return db.scalar(select(Suscripcion).where(Suscripcion.id_cuenta == id_cuenta)
                     .order_by(Suscripcion.fecha_inicio.desc()).limit(1))


def cuenta_out(db: Session, c: CuentaCliente) -> CuentaOut:
    s = _actual(db, c.id_cuenta)
    return CuentaOut(id_cuenta=c.id_cuenta, tipo_cuenta=c.tipo_cuenta, nombre=c.nombre, email_facturacion=c.email_facturacion,
                     rut=c.rut, estado=c.estado, titular=c.titular.nombre, titular_email=c.titular.email,
                     fecha_creacion=c.fecha_creacion, suscripcion_actual=sus_out(s) if s else None)


def tx_out(t: TransaccionPago) -> TransaccionOut:
    reemb = sum(r.monto for r in t.reembolsos)
    return TransaccionOut(id_transaccion=t.id_transaccion, id_suscripcion=t.id_suscripcion,
                          cuenta=t.suscripcion.cuenta.nombre, plan=t.suscripcion.plan.nombre, monto=t.monto,
                          moneda=t.moneda, estado=t.estado, fecha=t.fecha, medio_pago=t.medio_pago,
                          codigo_error=t.codigo_error, id_externo_pasarela=t.id_externo_pasarela, reembolsado=reemb,
                          reembolsable=t.monto - reemb if t.estado == "aprobada" else 0,
                          reembolsos=[ReembolsoOut(id_reembolso=r.id_reembolso, monto=r.monto, motivo=r.motivo,
                                                   estado=r.estado, autorizador=r.autorizador.nombre_completo, fecha=r.fecha)
                                      for r in t.reembolsos])


def _mes(d: datetime) -> datetime:
    return d + timedelta(days=30)


# ---------------------------------------------------------------- resumen
@router.get("/comercial/resumen", response_model=ResumenOut, summary="Resumen comercial actual")
def resumen(_: MiembroStaff = Depends(LECTURA), db: Session = Depends(get_db)):
    desde = utcnow() - timedelta(days=30)
    activas = db.scalars(select(Suscripcion).where(Suscripcion.estado == "activa")).all()
    return ResumenOut(
        mrr=sum(s.plan.precio for s in activas), suscripciones_activas=len(activas),
        en_mora=db.scalar(select(func.count()).where(Suscripcion.estado == "en_mora")),
        canceladas_30d=db.scalar(select(func.count()).where(Suscripcion.fecha_cancelacion >= desde)),
        ingresos_30d=db.scalar(select(func.coalesce(func.sum(TransaccionPago.monto), 0))
                               .where(TransaccionPago.estado == "aprobada", TransaccionPago.fecha >= desde)),
        reembolsos_30d=db.scalar(select(func.coalesce(func.sum(Reembolso.monto), 0)).where(Reembolso.fecha >= desde)),
        rechazos_30d=db.scalar(select(func.count()).where(TransaccionPago.estado == "rechazada",
                                                          TransaccionPago.fecha >= desde)))


# ---------------------------------------------------------------- CU09 planes
def plan_out(db: Session, p: Plan) -> PlanOut:
    return PlanOut(codigo_plan=p.codigo_plan, nombre=p.nombre, precio=p.precio, moneda=p.moneda,
                   unidad_facturable=p.unidad_facturable, periodicidad=p.periodicidad, activo=p.activo,
                   funcionalidades=[f.codigo_funcionalidad for f in p.funcionalidades],
                   suscripciones_activas=db.scalar(select(func.count()).where(Suscripcion.codigo_plan == p.codigo_plan,
                                                                              Suscripcion.estado == "activa")))


@router.get("/comercial/planes", response_model=list[PlanOut], summary="Planes comerciales")
def planes(_: MiembroStaff = Depends(LECTURA), db: Session = Depends(get_db)):
    return [plan_out(db, p) for p in db.scalars(select(Plan).order_by(Plan.orden))]


@router.get("/comercial/funcionalidades", response_model=list[FuncionalidadOut])
def funcionalidades(_: MiembroStaff = Depends(LECTURA), db: Session = Depends(get_db)):
    return [FuncionalidadOut(codigo=f.codigo_funcionalidad, nombre=f.nombre)
            for f in db.scalars(select(Funcionalidad).order_by(Funcionalidad.orden))]


@router.put("/comercial/planes/{codigo_plan}", response_model=PlanOut, summary="CU09 · Editar plan, precio y funcionalidades")
def editar_plan(codigo_plan: str, data: PlanIn, request: Request, staff: MiembroStaff = Depends(ESCRITURA),
                db: Session = Depends(get_db)):
    p = obtener(db, Plan, codigo_plan, "El plan")
    antes = {"nombre": p.nombre, "precio": p.precio, "activo": p.activo,
             "funcionalidades": sorted(f.codigo_funcionalidad for f in p.funcionalidades)}
    if data.precio is not None and codigo_plan == "gratuito" and data.precio != 0:
        raise ApiError(422, "FREE_PLAN", "El plan Gratuito siempre cuesta $0 (el adulto mayor nunca paga).")
    if data.activo is False and plan_out(db, p).suscripciones_activas:
        raise ApiError(409, "PLAN_IN_USE", "No se puede desactivar un plan con suscripciones activas.")
    for k in ("nombre", "precio", "activo"):
        if getattr(data, k) is not None:
            setattr(p, k, getattr(data, k))
    if data.funcionalidades is not None:
        validas = set(db.scalars(select(Funcionalidad.codigo_funcionalidad)))
        if not set(data.funcionalidades) <= validas:
            raise ApiError(422, "VALIDATION_ERROR", "Hay funcionalidades desconocidas.")
        p.funcionalidades = [PlanFuncionalidad(codigo_plan=codigo_plan, codigo_funcionalidad=f)
                             for f in sorted(set(data.funcionalidades))]
    db.flush()
    despues = {"nombre": p.nombre, "precio": p.precio, "activo": p.activo,
               "funcionalidades": sorted(f.codigo_funcionalidad for f in p.funcionalidades)}
    cambios = {k: v for k, v in despues.items() if antes[k] != v}
    if cambios:
        registrar(db, actor=staff, accion="plan.editar", tipo_entidad="plan", id_entidad=codigo_plan,
                  antes={k: antes[k] for k in cambios}, despues=cambios, request=request)
    db.commit()
    return plan_out(db, p)


# ---------------------------------------------------------------- CU10 cuentas
@router.get("/comercial/cuentas", response_model=Page[CuentaOut], summary="CU10 · Cuentas de clientes")
def cuentas(q: str | None = Query(None, max_length=120), tipo: str | None = None, page: int = Query(1, ge=1),
            page_size: int = Query(20, ge=1, le=100), _: MiembroStaff = Depends(LECTURA), db: Session = Depends(get_db)):
    stmt = select(CuentaCliente)
    if tipo:
        stmt = stmt.where(CuentaCliente.tipo_cuenta == tipo)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(func.lower(CuentaCliente.nombre).like(like), func.lower(CuentaCliente.email_facturacion).like(like),
                              CuentaCliente.rut.like(like)))
    return paginar(db, stmt.order_by(CuentaCliente.nombre), page, page_size, lambda c: cuenta_out(db, c))


@router.get("/comercial/cuentas/{id_cuenta}", response_model=CuentaDetalleOut)
def cuenta(id_cuenta: int, _: MiembroStaff = Depends(LECTURA), db: Session = Depends(get_db)):
    c = obtener(db, CuentaCliente, id_cuenta, "La cuenta")
    subs = db.scalars(select(Suscripcion).where(Suscripcion.id_cuenta == id_cuenta).order_by(Suscripcion.fecha_inicio.desc())).all()
    txs = db.scalars(select(TransaccionPago).where(TransaccionPago.id_suscripcion.in_([s.id_suscripcion for s in subs]))
                     .order_by(TransaccionPago.fecha.desc()).limit(24)).all()
    return CuentaDetalleOut(**cuenta_out(db, c).model_dump(), suscripciones=[sus_out(s) for s in subs],
                            transacciones=[tx_out(t) for t in txs])


@router.post("/comercial/cuentas", response_model=CuentaOut, status_code=201, summary="CU10 · Dar de alta una cuenta")
def crear_cuenta(data: CuentaIn, request: Request, staff: MiembroStaff = Depends(ESCRITURA), db: Session = Depends(get_db)):
    u = db.scalar(select(UsuarioApp).where(UsuarioApp.email == data.email_titular.lower()))
    if u is None:
        raise ApiError(404, "USER_NOT_FOUND", "El titular debe tener una cuenta en la app AgeCare.")
    c = CuentaCliente(id_usuario=u.id_usuario, tipo_cuenta=data.tipo_cuenta, nombre=data.nombre.strip(),
                      email_facturacion=data.email_facturacion.lower(), rut=data.rut)
    db.add(c)
    db.flush()
    if data.codigo_plan:
        plan = obtener(db, Plan, data.codigo_plan, "El plan")
        if not plan.activo:
            raise ApiError(409, "PLAN_INACTIVE", "El plan no está disponible.")
        now = utcnow()
        db.add(Suscripcion(id_cuenta=c.id_cuenta, codigo_plan=plan.codigo_plan, estado="activa", fecha_inicio=now,
                           inicio_periodo=now, fin_periodo=_mes(now), id_externo_pasarela=f"sub_{c.id_cuenta}_{int(now.timestamp())}"))
    registrar(db, actor=staff, accion="cuenta.crear", tipo_entidad="cuenta_cliente", id_entidad=c.id_cuenta,
              despues={"nombre": c.nombre, "tipo": c.tipo_cuenta, "plan": data.codigo_plan}, request=request)
    db.commit()
    db.refresh(c)
    return cuenta_out(db, c)


@router.patch("/comercial/cuentas/{id_cuenta}", response_model=CuentaOut)
def editar_cuenta(id_cuenta: int, data: CuentaUpdateIn, request: Request, staff: MiembroStaff = Depends(ESCRITURA),
                  db: Session = Depends(get_db)):
    c = obtener(db, CuentaCliente, id_cuenta, "La cuenta")
    cambios = data.model_dump(exclude_unset=True, exclude_none=True)
    antes = {k: getattr(c, k) for k in cambios}
    for k, v in cambios.items():
        setattr(c, k, v)
    if cambios:
        registrar(db, actor=staff, accion="cuenta.editar", tipo_entidad="cuenta_cliente", id_entidad=c.id_cuenta,
                  antes=antes, despues=cambios, request=request)
    db.commit()
    return cuenta_out(db, c)


# ---------------------------------------------------------------- CU11 / CU12 suscripciones
@router.get("/comercial/suscripciones", response_model=Page[SuscripcionOut], summary="CU11 · Suscripciones")
def suscripciones(estado: str | None = None, plan: str | None = None, page: int = Query(1, ge=1),
                  page_size: int = Query(20, ge=1, le=100), _: MiembroStaff = Depends(LECTURA), db: Session = Depends(get_db)):
    stmt = select(Suscripcion)
    if estado:
        stmt = stmt.where(Suscripcion.estado == estado)
    if plan:
        stmt = stmt.where(Suscripcion.codigo_plan == plan)
    return paginar(db, stmt.order_by(Suscripcion.fecha_inicio.desc()), page, page_size, sus_out)


@router.patch("/comercial/suscripciones/{id_suscripcion}/plan", response_model=SuscripcionOut,
              summary="CU11 · Cambiar el plan de una suscripción")
def cambiar_plan(id_suscripcion: int, data: CambioPlanIn, request: Request, staff: MiembroStaff = Depends(ESCRITURA),
                 db: Session = Depends(get_db)):
    s = obtener(db, Suscripcion, id_suscripcion, "La suscripción")
    if s.estado not in ("activa", "en_mora"):
        raise ApiError(409, "SUBSCRIPTION_CLOSED", "Solo se puede cambiar el plan de una suscripción vigente.")
    plan = obtener(db, Plan, data.codigo_plan, "El plan")
    if not plan.activo:
        raise ApiError(409, "PLAN_INACTIVE", "El plan no está disponible.")
    if plan.codigo_plan == s.codigo_plan:
        raise ApiError(409, "NO_CHANGE", "La suscripción ya tiene ese plan.")
    antes = s.codigo_plan
    s.codigo_plan = plan.codigo_plan  # el nuevo precio rige desde el próximo periodo
    registrar(db, actor=staff, accion="suscripcion.cambiar_plan", tipo_entidad="suscripcion", id_entidad=s.id_suscripcion,
              antes={"plan": antes}, despues={"plan": plan.codigo_plan}, request=request)
    db.commit()
    db.refresh(s)
    return sus_out(s)


@router.post("/comercial/suscripciones/{id_suscripcion}/cancelar", response_model=SuscripcionOut,
             summary="CU12 · Cancelar suscripción (vía pasarela)")
def cancelar(id_suscripcion: int, data: CancelarIn, request: Request, staff: MiembroStaff = Depends(ESCRITURA),
             db: Session = Depends(get_db)):
    s = obtener(db, Suscripcion, id_suscripcion, "La suscripción")
    if s.estado in ("cancelada", "vencida"):
        raise ApiError(409, "SUBSCRIPTION_CLOSED", "La suscripción ya no está vigente.")
    pasarela.cancelar_suscripcion(s.id_externo_pasarela)
    antes = s.estado
    s.estado, s.fecha_cancelacion, s.motivo_cancelacion = "cancelada", utcnow(), data.motivo.strip()
    registrar(db, actor=staff, accion="suscripcion.cancelar", tipo_entidad="suscripcion", id_entidad=s.id_suscripcion,
              antes={"estado": antes}, despues={"estado": "cancelada", "motivo": s.motivo_cancelacion}, request=request)
    db.commit()
    db.refresh(s)
    return sus_out(s)


# ---------------------------------------------------------------- CU13 / CU15 transacciones y reembolsos
@router.get("/comercial/transacciones", response_model=Page[TransaccionOut], summary="CU13 · Consultar transacciones")
def transacciones(estado: str | None = None, id_cuenta: int | None = None, dias: int = Query(90, ge=1, le=730),
                  page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
                  _: MiembroStaff = Depends(LECTURA), db: Session = Depends(get_db)):
    stmt = select(TransaccionPago).where(TransaccionPago.fecha >= utcnow() - timedelta(days=dias))
    if estado:
        stmt = stmt.where(TransaccionPago.estado == estado)
    if id_cuenta:
        stmt = stmt.join(Suscripcion).where(Suscripcion.id_cuenta == id_cuenta)
    return paginar(db, stmt.order_by(TransaccionPago.fecha.desc()), page, page_size, tx_out)


@router.get("/comercial/transacciones/{id_transaccion}", response_model=TransaccionOut)
def transaccion(id_transaccion: int, _: MiembroStaff = Depends(LECTURA), db: Session = Depends(get_db)):
    return tx_out(obtener(db, TransaccionPago, id_transaccion, "La transacción"))


@router.post("/comercial/transacciones/{id_transaccion}/reembolsos", response_model=TransaccionOut, status_code=201,
             summary="CU15 · Procesar reembolso (incluye CU13)")
def reembolsar(id_transaccion: int, data: ReembolsoIn, request: Request, staff: MiembroStaff = Depends(ESCRITURA),
               db: Session = Depends(get_db)):
    t = obtener(db, TransaccionPago, id_transaccion, "La transacción")  # «include» CU13: se consulta primero
    actual = tx_out(t)
    if t.estado != "aprobada":
        raise ApiError(409, "NOT_REFUNDABLE", "Solo se pueden reembolsar transacciones aprobadas.")
    if data.monto > actual.reembolsable:
        raise ApiError(422, "AMOUNT_EXCEEDED", f"El monto supera lo reembolsable (${actual.reembolsable:,}).".replace(",", "."))
    try:
        r = pasarela.reembolsar(t.id_externo_pasarela, data.monto)
    except pasarela.PasarelaError as e:
        raise ApiError(502, "GATEWAY_ERROR", f"La pasarela rechazó el reembolso: {e}")
    db.add(Reembolso(id_transaccion=t.id_transaccion, id_staff_autorizador=staff.id_staff, monto=data.monto,
                     motivo=data.motivo.strip(), estado=r["estado"], id_externo_pasarela=r["id"]))
    registrar(db, actor=staff, accion="pago.reembolsar", tipo_entidad="transaccion_pago", id_entidad=t.id_transaccion,
              despues={"monto": data.monto, "motivo": data.motivo}, request=request)
    db.commit()
    db.refresh(t)
    return tx_out(t)


@router.get("/comercial/eventos-pago", response_model=Page[EventoOut], summary="Eventos recibidos de la pasarela")
def eventos(page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100), _: MiembroStaff = Depends(LECTURA),
            db: Session = Depends(get_db)):
    return paginar(db, select(EventoPago).order_by(EventoPago.fecha_recepcion.desc()), page, page_size,
                   lambda e: EventoOut(id_evento=e.id_evento, id_externo_evento=e.id_externo_evento,
                                       tipo_evento=e.tipo_evento, id_transaccion=e.id_transaccion, procesado=e.procesado,
                                       error_procesamiento=e.error_procesamiento, fecha_recepcion=e.fecha_recepcion))


# ---------------------------------------------------------------- CU14 webhook (actor primario: Pasarela de pago)
class WebhookIn(BaseModel):
    id_evento: str = Field(min_length=3, max_length=100)
    tipo: Literal["pago.aprobado", "pago.rechazado"]
    id_suscripcion_externa: str
    id_transaccion_externa: str
    monto: int = Field(ge=0)
    medio_pago: str | None = None
    codigo_error: str | None = None


class WebhookOut(BaseModel):
    recibido: bool
    duplicado: bool
    procesado: bool
    error: str | None


@router.post("/pagos/webhook", response_model=WebhookOut, summary="CU14 · Registrar evento de pago (webhook firmado)")
async def webhook(request: Request, x_pasarela_firma: str | None = Header(None), db: Session = Depends(get_db)):
    cuerpo = await request.body()
    if not pasarela.firma_valida(cuerpo, x_pasarela_firma):
        raise ApiError(401, "INVALID_SIGNATURE", "Firma del webhook inválida.")
    try:
        data = WebhookIn.model_validate_json(cuerpo)
    except Exception:
        raise ApiError(422, "VALIDATION_ERROR", "Cuerpo del webhook inválido.")
    if db.scalar(select(EventoPago).where(EventoPago.id_externo_evento == data.id_evento)):
        return WebhookOut(recibido=True, duplicado=True, procesado=True, error=None)  # idempotencia
    ev = EventoPago(id_externo_evento=data.id_evento, tipo_evento=data.tipo, payload=json.dumps(data.model_dump()))
    db.add(ev)
    s = db.scalar(select(Suscripcion).where(Suscripcion.id_externo_pasarela == data.id_suscripcion_externa))
    if s is None:
        ev.error_procesamiento = "Suscripción desconocida"
    else:
        t = db.scalar(select(TransaccionPago).where(TransaccionPago.id_externo_pasarela == data.id_transaccion_externa))
        if t is None:
            t = TransaccionPago(id_suscripcion=s.id_suscripcion, monto=data.monto, id_externo_pasarela=data.id_transaccion_externa)
            db.add(t)
        t.medio_pago = data.medio_pago
        if data.tipo == "pago.aprobado":
            t.estado, t.codigo_error = "aprobada", None
            if s.estado in ("activa", "en_mora"):
                s.estado = "activa"
                s.inicio_periodo = max(s.fin_periodo, utcnow()) if s.fin_periodo < utcnow() else s.fin_periodo
                s.fin_periodo = _mes(s.inicio_periodo)
        else:
            t.estado, t.codigo_error = "rechazada", data.codigo_error or "rechazo_emisor"
            if s.estado == "activa":
                s.estado = "en_mora"
        db.flush()
        ev.id_transaccion, ev.procesado = t.id_transaccion, True
    registrar(db, actor=None, accion="pago.webhook", tipo_entidad="evento_pago", id_entidad=data.id_evento,
              despues={"tipo": data.tipo, "procesado": ev.procesado, "error": ev.error_procesamiento}, request=request)
    db.commit()
    return WebhookOut(recibido=True, duplicado=False, procesado=ev.procesado, error=ev.error_procesamiento)
