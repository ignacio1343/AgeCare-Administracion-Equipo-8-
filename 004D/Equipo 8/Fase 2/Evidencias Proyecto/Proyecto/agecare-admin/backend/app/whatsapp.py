"""Avisos de salud por WhatsApp al familiar del paciente (actor secundario: WhatsApp Business Cloud API de Meta).

Flujo
-----
1. La Plataforma AgeCare informa un evento de salud (lectura de signo vital, caída o SOS) → `registrar_evento`.
2. La lectura se compara con los umbrales del semáforo (CU05). Verde no genera alerta; amarillo genera una alerta
   media; rojo, caída y SOS generan una alerta **crítica**.
3. Cada alerta crítica deja un aviso por cada familiar del círculo de cuidado (`encolar_avisos`). Se envía solo si:
   el parámetro `whatsapp_activo` está encendido, el plan del paciente incluye la funcionalidad `alertas_whatsapp`,
   el familiar dio su consentimiento y tiene teléfono, y no recibió otro aviso del mismo paciente en los últimos
   `whatsapp_minutos_entre_avisos`. Si no se cumple, el aviso queda «omitido» con el motivo (trazabilidad).
4. Los avisos pendientes se envían de inmediato (tarea en segundo plano) y el planificador reintenta los que fallaron
   (1, 5 y 15 minutos). Tras `whatsapp_max_intentos` quedan «fallidos».
5. Meta informa por webhook (firmado con HMAC-SHA256) si el mensaje se entregó o se leyó.

Modos (`WHATSAPP_MODO`): «simulado» (por defecto, no llama a Meta) o «meta» (API real; requiere token, id del número
y una plantilla aprobada, porque un aviso iniciado por la empresa fuera de la ventana de 24 h exige plantilla).
"""
import hashlib
import hmac
import json
import logging
import re
import secrets
import urllib.error
import urllib.request
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import utcnow
from .models import (ORDEN_WHATSAPP, Alerta, CuentaCliente, MembresiaCirculo, MensajeWhatsapp, Paciente,
                     ParametroSistema, PlanFuncionalidad, Suscripcion, UmbralAlerta, UsuarioApp)

log = logging.getLogger("whatsapp")

FUNCIONALIDAD = "alertas_whatsapp"
TELEFONO_RE = re.compile(r"^\+[1-9]\d{7,14}$")  # E.164
REINTENTOS_MIN = (1, 5, 15)
SIGNOS = {"frecuencia_cardiaca": "frecuencia cardíaca", "saturacion_o2": "saturación de oxígeno",
          "presion_sistolica": "presión sistólica", "presion_diastolica": "presión diastólica",
          "temperatura": "temperatura", "glucosa": "glucosa"}
EVENTOS = {"caida": "posible caída detectada", "sos": "activó el botón SOS"}


class ErrorEnvio(Exception):
    def __init__(self, mensaje: str, reintentable: bool = True):
        super().__init__(mensaje)
        self.reintentable = reintentable


# ---------------------------------------------------------------- utilidades
def normalizar_telefono(tel: str | None) -> str | None:
    """Acepta «+56 9 1234 5678», «56912345678» o «912345678» (Chile) y devuelve E.164 o None si no es válido."""
    if not tel:
        return None
    t = re.sub(r"[\s\-().]", "", tel)
    if re.fullmatch(r"9\d{8}", t):
        t = "+56" + t
    elif re.fullmatch(r"56\d{9}", t):
        t = "+" + t
    return t if TELEFONO_RE.match(t) else None


def enmascarar(tel: str | None) -> str | None:
    return f"{tel[:4]} •••• {tel[-4:]}" if tel and len(tel) > 8 else tel


def _param(db: Session, clave: str, defecto: str) -> str:
    p = db.get(ParametroSistema, clave)
    return p.valor if p else defecto


def activo(db: Session) -> bool:
    return _param(db, "whatsapp_activo", "true").lower() == "true"


def _num(db: Session, clave: str, defecto: int) -> int:
    try:
        return int(float(_param(db, clave, str(defecto))))
    except ValueError:
        return defecto


def plan_del_paciente(db: Session, id_paciente: int) -> str | None:
    """Plan con más funcionalidades entre las suscripciones activas de los titulares del círculo del paciente."""
    titulares = select(MembresiaCirculo.id_usuario).where(MembresiaCirculo.id_paciente == id_paciente)
    planes = db.scalars(select(Suscripcion.codigo_plan).join(CuentaCliente)
                        .where(CuentaCliente.id_usuario.in_(titulares), Suscripcion.estado.in_(("activa", "en_mora")))).all()
    con_whatsapp = [p for p in planes if db.get(PlanFuncionalidad, (p, FUNCIONALIDAD))]
    return (con_whatsapp or planes or [None])[0]


def plan_incluye_whatsapp(db: Session, codigo_plan: str | None) -> bool:
    return bool(codigo_plan) and db.get(PlanFuncionalidad, (codigo_plan, FUNCIONALIDAD)) is not None


# ---------------------------------------------------------------- evaluación de eventos de salud
def nivel_de_lectura(db: Session, signo: str, valor: float) -> str | None:
    """Semáforo: dentro de verde → verde; dentro de amarillo → amarillo; fuera de amarillo → rojo."""
    verde = db.get(UmbralAlerta, (signo, "verde"))
    amarillo = db.get(UmbralAlerta, (signo, "amarillo"))
    if verde is None or amarillo is None:
        return None
    if float(verde.valor_minimo) <= valor <= float(verde.valor_maximo):
        return "verde"
    if float(amarillo.valor_minimo) <= valor <= float(amarillo.valor_maximo):
        return "amarillo"
    return "rojo"


def registrar_evento(db: Session, id_paciente: int, tipo: str, signo: str | None = None,
                     valor: float | None = None) -> tuple[Alerta | None, str | None, list[MensajeWhatsapp]]:
    """Crea la alerta que corresponde al evento y encola los avisos. Devuelve (alerta, nivel, avisos)."""
    nivel = None
    if tipo == "vital":
        nivel = nivel_de_lectura(db, signo or "", float(valor))
        if nivel is None:
            raise ValueError(f"No hay umbrales configurados para «{signo}».")
        if nivel == "verde":
            return None, nivel, []
        severidad = "critica" if nivel == "rojo" else "media"
    else:
        severidad = "critica"
    alerta = Alerta(id_paciente=id_paciente, codigo_tipo=tipo, severidad=severidad, signo_vital=signo,
                    valor=valor, nivel_semaforo=nivel)
    db.add(alerta)
    db.flush()
    db.refresh(alerta)
    avisos = encolar_avisos(db, alerta) if severidad == "critica" else []
    return alerta, nivel, avisos


def describir_evento(db: Session, alerta: Alerta) -> str:
    if alerta.codigo_tipo == "vital" and alerta.signo_vital:
        nombre = SIGNOS.get(alerta.signo_vital, alerta.signo_vital.replace("_", " "))
        if _param(db, "whatsapp_incluir_valor", "true").lower() == "true" and alerta.valor is not None:
            u = db.get(UmbralAlerta, (alerta.signo_vital, "verde"))
            unidad = f" {u.unidad}" if u else ""
            v = f"{float(alerta.valor):g}".replace(".", ",")
            return f"{nombre} {v}{unidad} (fuera de rango)"
        return f"{nombre} fuera de rango"
    return EVENTOS.get(alerta.codigo_tipo, alerta.tipo.nombre.lower() if alerta.tipo else alerta.codigo_tipo)


def _hora_local(dt: datetime) -> str:
    from zoneinfo import ZoneInfo
    return dt.astimezone(ZoneInfo(get_settings().zona_horaria)).strftime("%d-%m %H:%M")


def parametros_plantilla(db: Session, alerta: Alerta) -> list[str]:
    """Variables {{1}} paciente, {{2}} evento y {{3}} hora de la plantilla aprobada en Meta."""
    return [alerta.paciente.nombre, describir_evento(db, alerta), _hora_local(alerta.fecha_emision)]


def texto_aviso(params: list[str]) -> str:
    """Mismo texto que la plantilla registrada en Meta (ver docs/WHATSAPP.md)."""
    return (f"AgeCare · Aviso de salud de {params[0]}: {params[1]}. Hora: {params[2]}. "
            "Revisa la app AgeCare o comunícate con la cuidadora.")


# ---------------------------------------------------------------- encolado
def encolar_avisos(db: Session, alerta: Alerta, ahora: datetime | None = None) -> list[MensajeWhatsapp]:
    """`ahora` permite al seed reconstruir avisos históricos con la misma lógica."""
    if not activo(db):
        return []
    st = get_settings()
    ahora = ahora or utcnow()
    params = parametros_plantilla(db, alerta)
    contenido = texto_aviso(params)
    plan = plan_del_paciente(db, alerta.id_paciente)
    con_plan = plan_incluye_whatsapp(db, plan)
    ventana = ahora - timedelta(minutes=_num(db, "whatsapp_minutos_entre_avisos", 30))
    familiares = db.scalars(select(UsuarioApp).join(MembresiaCirculo)
                            .where(MembresiaCirculo.id_paciente == alerta.id_paciente,
                                   MembresiaCirculo.rol_en_circulo == "familiar",
                                   MembresiaCirculo.estado == "activo")
                            .order_by(UsuarioApp.id_usuario)).all()
    avisos = []
    for u in familiares:
        motivo = None
        if u.estado_cuenta != "activa":
            motivo = "La cuenta del familiar está desactivada."
        elif not con_plan:
            motivo = f"El plan del paciente ({plan or 'sin suscripción'}) no incluye avisos por WhatsApp."
        elif not u.whatsapp_habilitado:
            motivo = "El familiar no ha autorizado recibir avisos por WhatsApp."
        elif not u.telefono:
            motivo = "El familiar no tiene un teléfono registrado."
        else:
            previo = db.scalar(select(MensajeWhatsapp.id_mensaje).where(
                MensajeWhatsapp.id_paciente == alerta.id_paciente, MensajeWhatsapp.id_usuario == u.id_usuario,
                MensajeWhatsapp.estado.in_(("pendiente", "enviado", "entregado", "leido")),
                MensajeWhatsapp.fecha_creacion >= ventana, MensajeWhatsapp.fecha_creacion <= ahora).limit(1))
            if previo:
                motivo = f"Agrupado: ya se avisó por este paciente hace menos de la ventana configurada (aviso #{previo})."
        m = MensajeWhatsapp(id_alerta=alerta.id_alerta, id_paciente=alerta.id_paciente, id_usuario=u.id_usuario,
                            telefono=u.telefono, plantilla=st.whatsapp_plantilla, contenido=contenido,
                            estado="omitido" if motivo else "pendiente", motivo=motivo, fecha_creacion=ahora,
                            proximo_intento=None if motivo else ahora)
        db.add(m)
        avisos.append(m)
    db.flush()
    return avisos


# ---------------------------------------------------------------- proveedor
# Errores frecuentes de Meta y qué hacer (se muestran en la bitácora junto al código)
AYUDA_ERRORES = {
    190: "El token venció o es inválido: genera un token permanente (usuario del sistema).",
    131030: "El número no está en la lista de destinatarios permitidos del número de prueba (API Setup → To).",
    132001: "La plantilla no existe o no está aprobada en ese idioma.",
    132000: "La cantidad de variables no coincide con la plantilla.",
    131026: "El número no tiene WhatsApp o no puede recibir mensajes.",
    131047: "Fuera de la ventana de 24 h: solo se pueden enviar plantillas.",
    100: "Parámetro inválido (revisa WHATSAPP_PHONE_NUMBER_ID y el formato del teléfono).",
    10: "La app no tiene el permiso whatsapp_business_messaging.",
}
SIN_VARIABLES = {"hello_world": "en_US"}  # plantillas de ejemplo de Meta, aprobadas de fábrica


def _graph(metodo: str, ruta: str, cuerpo: dict | None = None) -> dict:
    """Llama a la Graph API de Meta. Lanza ErrorEnvio con el código y una ayuda legible."""
    st = get_settings()
    if not st.whatsapp_token:
        raise ErrorEnvio("Falta WHATSAPP_TOKEN.", reintentable=False)
    url = f"https://graph.facebook.com/{st.whatsapp_api_version}/{ruta}"
    req = urllib.request.Request(url, data=json.dumps(cuerpo).encode() if cuerpo is not None else None, method=metodo,
                                 headers={"Authorization": f"Bearer {st.whatsapp_token}",
                                          "Content-Type": "application/json"})
    try:
        # La URL base es fija (https://graph.facebook.com); no depende de datos del usuario
        with urllib.request.urlopen(req, timeout=10) as r:  # nosec B310
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read()).get("error", {})
        except (ValueError, AttributeError):
            err = {}
        codigo = err.get("code", "-")
        ayuda = AYUDA_ERRORES.get(codigo) or AYUDA_ERRORES.get(err.get("error_subcode"), "")
        msg = f"Meta {e.code}: {err.get('message', e.reason)} (código {codigo})" + (f". {ayuda}" if ayuda else "")
        raise ErrorEnvio(msg, reintentable=e.code == 429 or e.code >= 500) from None
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        raise ErrorEnvio(f"Sin respuesta válida de Meta: {type(e).__name__}") from None


def _enviar_meta(m: MensajeWhatsapp, params: list[str]) -> str:
    st = get_settings()
    if not (st.whatsapp_token and st.whatsapp_phone_number_id):
        raise ErrorEnvio("Faltan WHATSAPP_TOKEN o WHATSAPP_PHONE_NUMBER_ID.", reintentable=False)
    if st.whatsapp_plantilla in SIN_VARIABLES:  # prueba de conexión mientras Meta aprueba la plantilla propia
        plantilla = {"name": st.whatsapp_plantilla, "language": {"code": SIN_VARIABLES[st.whatsapp_plantilla]}}
    else:
        plantilla = {"name": st.whatsapp_plantilla, "language": {"code": st.whatsapp_idioma},
                     "components": [{"type": "body", "parameters": [{"type": "text", "text": p} for p in params]}]}
    cuerpo = {"messaging_product": "whatsapp", "recipient_type": "individual", "to": m.telefono.lstrip("+"),
              "type": "template", "template": plantilla}
    try:
        return _graph("POST", f"{st.whatsapp_phone_number_id}/messages", cuerpo)["messages"][0]["id"]
    except (KeyError, IndexError, TypeError):
        raise ErrorEnvio("Meta respondió sin id de mensaje.") from None


def diagnostico() -> dict:
    """Comprueba la configuración real con Meta sin enviar mensajes: número emisor, token y estado de la plantilla."""
    st = get_settings()
    out = {"modo": st.whatsapp_modo, "api_version": st.whatsapp_api_version, "plantilla": st.whatsapp_plantilla,
           "idioma": SIN_VARIABLES.get(st.whatsapp_plantilla, st.whatsapp_idioma),
           "token": bool(st.whatsapp_token), "phone_number_id": bool(st.whatsapp_phone_number_id),
           "app_secret": bool(st.whatsapp_app_secret), "verify_token": bool(st.whatsapp_verify_token),
           "waba_id": bool(st.whatsapp_waba_id), "numero": None, "plantilla_estado": None, "errores": []}
    if st.whatsapp_modo != "meta":
        out["errores"].append("WHATSAPP_MODO no es «meta»: los avisos se simulan.")
        return out
    if st.whatsapp_phone_number_id:
        try:
            n = _graph("GET", f"{st.whatsapp_phone_number_id}?fields=display_phone_number,verified_name,quality_rating")
            out["numero"] = {"telefono": n.get("display_phone_number"), "nombre": n.get("verified_name"),
                             "calidad": n.get("quality_rating")}
        except ErrorEnvio as e:
            out["errores"].append(f"Número emisor: {e}")
    else:
        out["errores"].append("Falta WHATSAPP_PHONE_NUMBER_ID.")
    if st.whatsapp_plantilla in SIN_VARIABLES:
        out["plantilla_estado"] = "APPROVED (plantilla de ejemplo de Meta)"
    elif st.whatsapp_waba_id:
        try:
            t = _graph("GET", f"{st.whatsapp_waba_id}/message_templates?name={st.whatsapp_plantilla}&fields=name,language,status")
            filas = [x for x in t.get("data", []) if x.get("name") == st.whatsapp_plantilla]
            idioma = [x for x in filas if x.get("language") == st.whatsapp_idioma]
            out["plantilla_estado"] = (idioma or filas or [{}])[0].get("status") or "NO EXISTE"
            if filas and not idioma:
                out["errores"].append(f"La plantilla existe, pero no en el idioma «{st.whatsapp_idioma}».")
        except ErrorEnvio as e:
            out["errores"].append(f"Plantilla: {e}")
    if not st.whatsapp_app_secret or not st.whatsapp_verify_token:
        out["errores"].append("Sin WHATSAPP_APP_SECRET o WHATSAPP_VERIFY_TOKEN no llegan los estados entregado/leído.")
    return out


def _enviar_simulado(m: MensajeWhatsapp) -> str:
    if m.telefono.endswith("0000"):  # número de prueba que simula un teléfono sin WhatsApp
        raise ErrorEnvio("Simulación: el número no tiene WhatsApp o no está disponible.")
    return f"wamid.SIM{secrets.token_hex(12)}"


def enviar(db: Session, m: MensajeWhatsapp) -> None:
    """Intenta enviar un aviso pendiente y deja el resultado en el registro (no hace commit)."""
    st = get_settings()
    m.intentos += 1
    try:
        params = parametros_plantilla(db, m.alerta) if m.alerta else [m.paciente.nombre, "mensaje de prueba de la consola, no hay una emergencia", _hora_local(utcnow())]
        wamid = _enviar_meta(m, params) if st.whatsapp_modo == "meta" else _enviar_simulado(m)
    except ErrorEnvio as e:
        maximo = _num(db, "whatsapp_max_intentos", 3)
        m.motivo = str(e)[:300]
        if not e.reintentable or m.intentos >= maximo:
            m.estado, m.proximo_intento = "fallido", None
            log.warning("aviso %s fallido tras %s intentos: %s", m.id_mensaje, m.intentos, m.motivo)
        else:
            espera = REINTENTOS_MIN[min(m.intentos - 1, len(REINTENTOS_MIN) - 1)]
            m.proximo_intento = utcnow() + timedelta(minutes=espera)
            log.info("aviso %s: intento %s falló, se reintenta en %s min", m.id_mensaje, m.intentos, espera)
        return
    m.estado, m.id_mensaje_proveedor, m.fecha_envio, m.proximo_intento, m.motivo = "enviado", wamid, utcnow(), None, None
    log.info("aviso %s enviado a %s (%s)", m.id_mensaje, enmascarar(m.telefono), st.whatsapp_modo)


def procesar_pendientes(db: Session, limite: int = 50) -> int:
    """Envía los avisos pendientes cuyo próximo intento ya llegó. Lo llaman la API (al crear la alerta) y el planificador."""
    ahora = utcnow()
    pendientes = db.scalars(select(MensajeWhatsapp).where(MensajeWhatsapp.estado == "pendiente",
                                                          MensajeWhatsapp.proximo_intento <= ahora)
                            .order_by(MensajeWhatsapp.id_mensaje).limit(limite)).all()
    for m in pendientes:
        enviar(db, m)
    if get_settings().whatsapp_modo != "meta":
        _simular_estados(db, ahora)
    db.commit()
    return len(pendientes)


def _simular_estados(db: Session, ahora: datetime) -> None:
    """En modo simulado imita los webhooks de Meta: entregado a los 30 s y leído (7 de cada 10) a los 2 min."""
    for m in db.scalars(select(MensajeWhatsapp).where(MensajeWhatsapp.estado.in_(("enviado", "entregado")),
                                                      MensajeWhatsapp.id_mensaje_proveedor.like("wamid.SIM%"))):
        if m.estado == "enviado" and m.fecha_envio and m.fecha_envio <= ahora - timedelta(seconds=30):
            m.estado, m.fecha_entrega = "entregado", ahora
        elif m.estado == "entregado" and m.fecha_entrega and m.fecha_entrega <= ahora - timedelta(minutes=2) \
                and m.id_mensaje % 10 < 7:
            m.estado, m.fecha_lectura = "leido", ahora


# ---------------------------------------------------------------- webhook de Meta
def firma_valida(cuerpo: bytes, firma: str | None) -> bool:
    secreto = get_settings().whatsapp_app_secret
    if not secreto or not firma or not firma.startswith("sha256="):
        return False
    esperado = hmac.new(secreto.encode(), cuerpo, hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, firma[7:])


def aplicar_estados(db: Session, payload: dict) -> int:
    """Procesa `entry[].changes[].value.statuses[]`. Los estados nunca retroceden; los duplicados no cambian nada."""
    cambios = 0
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            for s in change.get("value", {}).get("statuses", []):
                m = db.scalar(select(MensajeWhatsapp).where(MensajeWhatsapp.id_mensaje_proveedor == s.get("id")))
                if m is None:
                    continue
                nuevo = {"sent": "enviado", "delivered": "entregado", "read": "leido", "failed": "fallido"}.get(s.get("status"))
                try:
                    cuando = datetime.fromtimestamp(int(s.get("timestamp")), tz=utcnow().tzinfo)
                except (TypeError, ValueError):
                    cuando = utcnow()
                if nuevo == "fallido" and m.estado in ("pendiente", "enviado"):
                    err = (s.get("errors") or [{}])[0]
                    m.estado, m.motivo = "fallido", f"Meta {err.get('code', '')}: {err.get('title', 'falló la entrega')}"[:300]
                    cambios += 1
                elif nuevo in ORDEN_WHATSAPP and ORDEN_WHATSAPP.get(m.estado, -1) < ORDEN_WHATSAPP[nuevo]:
                    m.estado = nuevo
                    if nuevo == "entregado":
                        m.fecha_entrega = cuando
                    elif nuevo == "leido":
                        m.fecha_lectura = cuando
                        m.fecha_entrega = m.fecha_entrega or cuando
                    cambios += 1
    db.commit()
    return cambios


def paciente_existe(db: Session, id_paciente: int) -> Paciente | None:
    return db.get(Paciente, id_paciente)
