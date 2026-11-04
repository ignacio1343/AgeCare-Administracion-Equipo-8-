"""Código de verificación por correo al registrarse un representante (actor secundario: servicio de correo).

El plan gratuito de Render bloquea los puertos SMTP (25, 465 y 587), así que el correo sale por HTTPS.

Modos (`CORREO_MODO`):
- «apps_script» (recomendado): un Google Apps Script publicado como aplicación web en el Gmail del equipo envía el
  correo con MailApp (gratis, ~100 destinatarios al día en una cuenta Gmail). Requiere CORREO_SCRIPT_URL y
  CORREO_SCRIPT_CLAVE (clave compartida que el script comprueba). Ver docs/PORTAL.md y docs/apps_script_correo.gs.
- «brevo»: API HTTPS de Brevo. Requiere BREVO_API_KEY y CORREO_REMITENTE (correo verificado en Brevo).
- «simulado»: no envía nada y devuelve el código; solo para el entorno local y las pruebas automáticas.
La API genera el código y guarda solo su hash; el código nunca queda en los registros técnicos.
"""
import html
import json
import logging
import secrets
import urllib.error
import urllib.request

from .config import get_settings
from .security import sha256

log = logging.getLogger("correo")
BREVO_URL = "https://api.brevo.com/v3/smtp/email"


class ErrorCorreo(Exception):
    pass


def modo() -> str:
    m = get_settings().correo_modo.lower()
    return m if m in ("brevo", "apps_script") else "simulado"


def enmascarar(email: str) -> str:
    """«carolina.gutierrez@gmail.com» → «ca•••@gmail.com»."""
    usuario, _, dominio = email.partition("@")
    return f"{usuario[:2]}•••@{dominio}"


def nuevo_codigo() -> tuple[str, str]:
    codigo = f"{secrets.randbelow(1_000_000):06d}"
    return codigo, sha256(codigo)


def comprobar(codigo: str, codigo_hash: str | None) -> bool:
    return bool(codigo_hash) and secrets.compare_digest(sha256(codigo), codigo_hash)


def _html(nombre: str, codigo: str, minutos: int) -> str:
    n = html.escape(nombre)
    return f"""<div style="font-family:Arial,Helvetica,sans-serif;max-width:480px;margin:0 auto;color:#1d2430">
  <div style="background:#2f63c8;color:#fff;padding:18px 22px;border-radius:14px 14px 0 0;font-size:20px;font-weight:bold">AgeCare</div>
  <div style="border:1px solid #e6e1d8;border-top:none;border-radius:0 0 14px 14px;padding:22px">
    <p style="font-size:16px">Hola, {n}:</p>
    <p style="font-size:16px">Tu código para confirmar tu cuenta de representante en AgeCare es:</p>
    <p style="font-size:34px;font-weight:bold;letter-spacing:8px;text-align:center;background:#f5f3ef;border-radius:12px;padding:14px 0;margin:18px 0">{codigo}</p>
    <p style="font-size:14px;color:#556070">Vence en {minutos} minutos. Si no pediste crear una cuenta, ignora este correo.</p>
    <p style="font-size:12px;color:#87909c;margin-top:22px">AgeCare · Wellq Co. Nunca te pediremos este código por teléfono.</p>
  </div>
</div>"""


def _apps_script(email: str, nombre: str, codigo: str, minutos: int) -> None:
    st = get_settings()
    if not st.correo_script_url.startswith("https://script.google.com/") or not st.correo_script_clave:
        raise ErrorCorreo("El envío de correos no está configurado (faltan CORREO_SCRIPT_URL o CORREO_SCRIPT_CLAVE).")
    cuerpo = {"clave": st.correo_script_clave, "para": email, "asunto": f"{codigo} es tu código de AgeCare",
              "html": _html(nombre, codigo, minutos), "remitente": st.correo_remitente_nombre or "AgeCare",
              "texto": f"Hola, {nombre}: tu código para confirmar tu cuenta en AgeCare es {codigo}. "
                       f"Vence en {minutos} minutos."}
    req = urllib.request.Request(st.correo_script_url, method="POST", data=json.dumps(cuerpo).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        # Solo URLs https://script.google.com/ (validado arriba). Google responde 302 y urllib sigue la redirección
        with urllib.request.urlopen(req, timeout=20) as r:  # nosec B310
            crudo = r.read()
    except urllib.error.HTTPError as e:
        raise ErrorCorreo(f"El script de Google respondió {e.code}. Revisa que la implementación sea «Cualquier "
                          "usuario» y que la URL termine en /exec.") from None
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        raise ErrorCorreo(f"No se pudo conectar con el script de Google: {e}") from None
    try:
        resp = json.loads(crudo)
    except ValueError:
        raise ErrorCorreo("El script de Google no respondió JSON: revisa que esté implementado como «Aplicación web», "
                          "con acceso «Cualquier usuario», y que autorizaste el envío de correos.") from None
    if not resp.get("ok"):
        motivo = {"clave": "la clave no coincide con CORREO_SCRIPT_CLAVE"}.get(resp.get("error"), resp.get("error"))
        raise ErrorCorreo(f"El script de Google no envió el correo: {motivo}.")
    log.info("código de registro enviado a %s (Apps Script; quedan %s envíos hoy)", enmascarar(email),
             resp.get("restantes", "?"))


def enviar_codigo(email: str, nombre: str, codigo: str, minutos: int) -> None:
    """Envía el código por correo (apps_script o brevo). En modo simulado no hace nada."""
    if modo() == "simulado":
        log.info("correo simulado a %s", enmascarar(email))
        return
    if modo() == "apps_script":
        return _apps_script(email, nombre, codigo, minutos)
    st = get_settings()
    if not st.brevo_api_key or not st.correo_remitente:
        raise ErrorCorreo("El envío de correos no está configurado (faltan BREVO_API_KEY o CORREO_REMITENTE).")
    cuerpo = {
        "sender": {"email": st.correo_remitente, "name": st.correo_remitente_nombre or "AgeCare"},
        "to": [{"email": email, "name": nombre}],
        "subject": f"{codigo} es tu código de AgeCare",
        "htmlContent": _html(nombre, codigo, minutos),
        "textContent": f"Hola, {nombre}: tu código para confirmar tu cuenta en AgeCare es {codigo}. "
                       f"Vence en {minutos} minutos.",
        "tags": ["registro-representante"],
    }
    req = urllib.request.Request(BREVO_URL, method="POST", data=json.dumps(cuerpo).encode(),
                                 headers={"api-key": st.brevo_api_key, "Content-Type": "application/json",
                                          "Accept": "application/json"})
    try:
        # URL fija de Brevo; no depende de datos del usuario
        with urllib.request.urlopen(req, timeout=10) as r:  # nosec B310
            r.read()
    except urllib.error.HTTPError as e:
        try:
            detalle = json.loads(e.read()).get("message", e.reason)
        except (ValueError, AttributeError):
            detalle = e.reason
        log.warning("Brevo respondió %s: %s", e.code, detalle)
        ayuda = {401: " Revisa BREVO_API_KEY o autoriza la IP en Brevo (Security → Authorised IPs).",
                 400: " Revisa que CORREO_REMITENTE esté verificado en Brevo (Senders)."}.get(e.code, "")
        raise ErrorCorreo(f"El servicio de correo rechazó el envío ({e.code}: {detalle}).{ayuda}") from None
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        raise ErrorCorreo(f"No se pudo conectar con el servicio de correo: {e}") from None
    log.info("código de registro enviado a %s", enmascarar(email))
