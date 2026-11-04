"""Reglas de negocio del portal web: vistas por perfil, planes, ficha vital, avisos dentro del portal y pagos.

Perfiles de la app y su vista en el portal:
  familiar      → «representante»: contrata y paga el plan de sus residentes, ve su estado y recibe avisos
  adulto_mayor  → «residente»: ve chistes, noticias y eventos; pide ayuda (no paga ni cambia planes)
  cuidadora     → «cuidador»: registra el estado vital (Normal / Alerta / Riesgoso) de los residentes asignados
"""
import secrets
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import utcnow
from .models import (Alerta, CuentaCliente, MembresiaCirculo, NotificacionApp, OrdenPago, Paciente, Plan,
                     PlanFuncionalidad, RegistroVital, Suscripcion, Ticket, TransaccionPago, UsuarioApp)

VISTAS = {"familiar": "representante", "adulto_mayor": "residente", "cuidadora": "cuidador"}
ROL_CIRCULO = {"representante": "familiar", "cuidador": "cuidadora"}
F_ESTADO = "estado_tiempo_real"   # Platino y Proveedor
F_AVISOS = "alertas_whatsapp"     # Dorado, Platino y Proveedor
ETIQUETA_ESTADO = {"normal": "Normal", "alerta": "Alerta", "riesgoso": "Riesgoso"}
VIGENTES = ("activa", "en_mora")


def vistas_de(u: UsuarioApp) -> list[str]:
    orden = ["representante", "cuidador", "residente"]
    vs = {VISTAS[p.codigo_perfil] for p in u.perfiles if p.codigo_perfil in VISTAS}
    return [v for v in orden if v in vs]


def nombre_completo(*partes: str | None) -> str:
    return " ".join(p.strip() for p in partes if p and p.strip())


def edad(nac: date | None) -> int | None:
    if not nac:
        return None
    h = date.today()
    return h.year - nac.year - ((h.month, h.day) < (nac.month, nac.day))


# ---------------------------------------------------------------- planes
def plan_incluye(db: Session, codigo_plan: str | None, funcionalidad: str) -> bool:
    return bool(codigo_plan) and db.get(PlanFuncionalidad, (codigo_plan, funcionalidad)) is not None


def suscripcion_de(db: Session, id_paciente: int) -> Suscripcion | None:
    """Suscripción propia del residente (la más reciente). Las del portal y la consola v0.6 la tienen."""
    return db.scalar(select(Suscripcion).where(Suscripcion.id_paciente == id_paciente)
                     .order_by(Suscripcion.fecha_inicio.desc()).limit(1))


def plan_vigente(db: Session, id_paciente: int) -> str | None:
    s = suscripcion_de(db, id_paciente)
    if s is not None:
        return s.codigo_plan if s.estado in VIGENTES else None
    # Datos anteriores a v0.6: el plan sale de las cuentas de los titulares del círculo
    titulares = select(MembresiaCirculo.id_usuario).where(MembresiaCirculo.id_paciente == id_paciente)
    planes = db.scalars(select(Suscripcion.codigo_plan).join(CuentaCliente)
                        .where(CuentaCliente.id_usuario.in_(titulares), Suscripcion.id_paciente.is_(None),
                               Suscripcion.estado.in_(VIGENTES))).all()
    con_avisos = [p for p in planes if plan_incluye(db, p, F_AVISOS)]
    return (con_avisos or planes or [None])[0]


def cuenta_familia(db: Session, u: UsuarioApp) -> CuentaCliente:
    c = db.scalar(select(CuentaCliente).where(CuentaCliente.id_usuario == u.id_usuario,
                                              CuentaCliente.tipo_cuenta == "familia").limit(1))
    if c is None:
        c = CuentaCliente(id_usuario=u.id_usuario, tipo_cuenta="familia", nombre=f"Familia {u.primer_apellido or u.nombre}",
                          email_facturacion=u.email, rut=u.rut)
        db.add(c)
        db.flush()
    return c


def nueva_suscripcion(db: Session, cuenta: CuentaCliente, codigo_plan: str, id_paciente: int | None = None,
                      ref: str | None = None) -> Suscripcion:
    now = utcnow()
    s = Suscripcion(id_cuenta=cuenta.id_cuenta, codigo_plan=codigo_plan, estado="activa", fecha_inicio=now,
                    inicio_periodo=now, fin_periodo=now + timedelta(days=30), id_paciente=id_paciente,
                    id_externo_pasarela=ref or f"sub_{cuenta.id_cuenta}_{secrets.token_hex(4)}")
    db.add(s)
    db.flush()
    return s


# ---------------------------------------------------------------- avisos dentro del portal
def notificar(db: Session, id_usuario: int, tipo: str, titulo: str, cuerpo: str, id_paciente: int | None = None):
    n = NotificacionApp(id_usuario=id_usuario, id_paciente=id_paciente, tipo=tipo, titulo=titulo[:160], cuerpo=cuerpo[:1000])
    db.add(n)
    return n


def representantes_de(db: Session, id_paciente: int) -> list[UsuarioApp]:
    return list(db.scalars(select(UsuarioApp).join(MembresiaCirculo)
                           .where(MembresiaCirculo.id_paciente == id_paciente, MembresiaCirculo.rol_en_circulo == "familiar",
                                  MembresiaCirculo.estado == "activo", UsuarioApp.estado_cuenta == "activa")
                           .order_by(UsuarioApp.id_usuario)))


def avisar_en_portal(db: Session, alerta: Alerta, detalle: str) -> int:
    """Alerta crítica → aviso en la vista de cada representante, si el plan incluye avisos de riesgo
    (Dorado, Platino o Proveedor; la misma regla que WhatsApp)."""
    if not plan_incluye(db, plan_vigente(db, alerta.id_paciente), F_AVISOS):
        return 0
    paciente = db.get(Paciente, alerta.id_paciente)
    reps = representantes_de(db, alerta.id_paciente)
    for u in reps:
        notificar(db, u.id_usuario, "estado_riesgoso" if alerta.codigo_tipo == "ficha_vital" else "alerta_salud",
                  f"⚠ {paciente.nombre}: estado de riesgo", detalle, alerta.id_paciente)
    return len(reps)


# ---------------------------------------------------------------- ficha vital (cuidador)
def registrar_ficha(db: Session, cuidador: UsuarioApp, paciente: Paciente, estado: str,
                    observacion: str) -> tuple[RegistroVital, int, int]:
    """Guarda el estado vital. «Alerta» deja una alerta media; «Riesgoso» una alerta crítica que avisa por WhatsApp
    y en el portal a los representantes (según el plan). Devuelve (registro, avisos WhatsApp, avisos en portal)."""
    from . import whatsapp
    reg = RegistroVital(id_paciente=paciente.id_paciente, id_usuario_cuidador=cuidador.id_usuario, estado=estado,
                        observacion=observacion.strip())
    db.add(reg)
    db.flush()
    n_wa = n_app = 0
    if estado in ("alerta", "riesgoso"):
        alerta = Alerta(id_paciente=paciente.id_paciente, codigo_tipo="ficha_vital",
                        severidad="critica" if estado == "riesgoso" else "media", nivel_semaforo=estado)
        db.add(alerta)
        db.flush()
        db.refresh(alerta)
        reg.id_alerta = alerta.id_alerta
        if estado == "riesgoso":
            n_wa = len([m for m in whatsapp.encolar_avisos(db, alerta) if m.estado == "pendiente"])
            n_app = avisar_en_portal(db, alerta, f"{cuidador.nombre} registró el estado Riesgoso: {reg.observacion}")
    return reg, n_wa, n_app


def ultimo_registro(db: Session, id_paciente: int) -> RegistroVital | None:
    return db.scalar(select(RegistroVital).where(RegistroVital.id_paciente == id_paciente)
                     .order_by(RegistroVital.fecha.desc(), RegistroVital.id_registro.desc()).limit(1))


def registro_out(r: RegistroVital) -> dict:
    return {"id_registro": r.id_registro, "estado": r.estado, "etiqueta": ETIQUETA_ESTADO[r.estado],
            "observacion": r.observacion, "cuidador": r.cuidador.nombre, "fecha": r.fecha}


# ---------------------------------------------------------------- tickets creados desde el portal
def crear_ticket(db: Session, categoria: str, asunto: str, descripcion: str, usuario: UsuarioApp | None = None,
                 nombre: str | None = None, email: str | None = None, prioridad: str = "media") -> Ticket:
    id_pac = None
    if usuario is not None:
        pac = db.scalar(select(Paciente.id_paciente).where(Paciente.id_usuario == usuario.id_usuario))
        id_pac = pac or (usuario.membresias[0].id_paciente if usuario.membresias else None)
    t = Ticket(codigo_categoria=categoria, id_usuario=usuario.id_usuario if usuario else None, id_paciente=id_pac,
               asunto=asunto[:160], descripcion=descripcion, prioridad=prioridad, canal="app", estado="abierto",
               nombre_solicitante=usuario.nombre if usuario else nombre, email_solicitante=usuario.email if usuario else email)
    db.add(t)
    db.flush()
    t.numero = 1000 + t.id_ticket
    return t


# ---------------------------------------------------------------- pagos
def nueva_orden_compra() -> str:
    return "ACA" + secrets.token_hex(8).upper()  # 19 caracteres (Webpay acepta hasta 26)


def aplicar_pago(db: Session, o: OrdenPago, aprobado: bool, *, autorizacion: str | None = None,
                 tarjeta: str | None = None, tipo_pago: str | None = None, codigo_respuesta: int | None = None,
                 detalle: str | None = None, proveedor_ref: str | None = None) -> None:
    """Aplica el resultado de la pasarela a la orden (idempotente: una orden cerrada no se vuelve a aplicar)."""
    if o.estado != "iniciada":
        return
    now = utcnow()
    o.fecha_confirmacion, o.codigo_autorizacion, o.tarjeta = now, autorizacion, tarjeta
    o.tipo_pago, o.codigo_respuesta, o.detalle = tipo_pago, codigo_respuesta, detalle
    medio = f"Webpay · tarjeta ****{tarjeta}" if tarjeta else ("Pago simulado" if o.proveedor == "simulado" else "Webpay")
    s = db.get(Suscripcion, o.id_suscripcion) if o.id_suscripcion else None
    if not aprobado:
        o.estado = "rechazada"
        if s is not None:
            t = TransaccionPago(id_suscripcion=s.id_suscripcion, monto=o.monto, estado="rechazada", medio_pago=medio,
                                codigo_error=f"webpay_{codigo_respuesta}" if codigo_respuesta is not None else "rechazo",
                                id_externo_pasarela=f"tx_{o.orden_compra}")
            db.add(t)
            db.flush()
            o.id_transaccion = t.id_transaccion
        notificar(db, o.id_usuario, "pago", "Pago rechazado",
                  f"El pago de ${o.monto:,} del plan {o.plan.nombre} fue rechazado. Puedes intentarlo de nuevo."
                  .replace(",", "."))
        return
    o.estado = "aprobada"
    if o.tipo == "alta":
        cuenta = cuenta_familia(db, o.usuario)
        s = nueva_suscripcion(db, cuenta, o.codigo_plan, o.id_paciente, ref=f"sub_{o.orden_compra}")
        o.id_suscripcion = s.id_suscripcion
    elif o.tipo == "renovacion" and s is not None:
        s.inicio_periodo = max(s.fin_periodo, now)
        s.fin_periodo = s.inicio_periodo + timedelta(days=30)
        s.estado = "activa"
    elif o.tipo == "cambio" and s is not None:
        s.codigo_plan, s.inicio_periodo, s.fin_periodo, s.estado = o.codigo_plan, now, now + timedelta(days=30), "activa"
    t = TransaccionPago(id_suscripcion=o.id_suscripcion, monto=o.monto, estado="aprobada", medio_pago=medio,
                        id_externo_pasarela=proveedor_ref or f"tx_{o.orden_compra}")
    db.add(t)
    db.flush()
    o.id_transaccion = t.id_transaccion
    siguiente = ("Ahora puedes registrar a tu residente." if o.tipo == "alta" and not (s and s.id_paciente)
                 else "Tu plan quedó activo por 30 días.")
    notificar(db, o.id_usuario, "pago", "Pago aprobado",
              f"Pagaste ${o.monto:,} por el plan {o.plan.nombre}. {siguiente}".replace(",", "."))


def plan_activo(db: Session, codigo: str) -> Plan | None:
    p = db.get(Plan, codigo)
    return p if p and p.activo else None

