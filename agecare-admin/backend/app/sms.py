"""Código de verificación por SMS al registrarse un representante (actor secundario: proveedor de SMS).

Modos (`SMS_MODO`):
- «simulado» (por defecto): genera un código de 6 dígitos, guarda solo su hash y lo devuelve para mostrarlo en
  pantalla con el aviso «modo demo». La demo y el CI nunca dependen de un proveedor externo.
- «twilio»: Twilio Verify envía y valida el código (Twilio lo genera y lo guarda; la API solo pregunta si es correcto).
  Requiere TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN y TWILIO_VERIFY_SID. En una cuenta de prueba de Twilio solo llega
  a los números verificados en la consola de Twilio.
"""
import base64
import json
import logging
import secrets
import urllib.error
import urllib.parse
import urllib.request

from .config import get_settings
from .security import sha256

log = logging.getLogger("sms")
VERIFY = "https://verify.twilio.com/v2/Services"


class ErrorSms(Exception):
    pass


def modo() -> str:
    return "twilio" if get_settings().sms_modo.lower() == "twilio" else "simulado"


def _twilio(ruta: str, campos: dict) -> dict:
    st = get_settings()
    if not (st.twilio_account_sid and st.twilio_auth_token and st.twilio_verify_sid):
        raise ErrorSms("Faltan las credenciales de Twilio (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_VERIFY_SID).")
    auth = base64.b64encode(f"{st.twilio_account_sid}:{st.twilio_auth_token}".encode()).decode()
    req = urllib.request.Request(f"{VERIFY}/{st.twilio_verify_sid}/{ruta}", method="POST",
                                 data=urllib.parse.urlencode(campos).encode(),
                                 headers={"Authorization": f"Basic {auth}",
                                          "Content-Type": "application/x-www-form-urlencoded"})
    try:
        # URL base fija (https://verify.twilio.com); no depende de datos del usuario
        with urllib.request.urlopen(req, timeout=10) as r:  # nosec B310
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        if e.code == 404 and ruta == "VerificationCheck":
            return {"status": "expired"}  # Twilio responde 404 si el código venció o ya se usó
        try:
            detalle = json.loads(e.read()).get("message", e.reason)
        except (ValueError, AttributeError):
            detalle = e.reason
        log.warning("Twilio %s respondió %s: %s", ruta, e.code, detalle)
        raise ErrorSms(f"El proveedor de SMS rechazó la solicitud ({e.code}): {detalle}") from None
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        raise ErrorSms(f"No se pudo conectar con el proveedor de SMS: {e}") from None


def enviar(telefono: str) -> tuple[str | None, str | None]:
    """Envía un código al teléfono (E.164). Devuelve (hash del código, código visible) en modo simulado;
    (None, None) con Twilio."""
    if modo() == "twilio":
        _twilio("Verifications", {"To": telefono, "Channel": "sms", "Locale": "es"})
        return None, None
    codigo = f"{secrets.randbelow(1_000_000):06d}"
    log.info("SMS simulado a %s•••%s", telefono[:4], telefono[-2:])
    return sha256(codigo), codigo


def comprobar(telefono: str, codigo: str, codigo_hash: str | None) -> bool:
    if modo() == "twilio":
        return _twilio("VerificationCheck", {"To": telefono, "Code": codigo}).get("status") == "approved"
    return bool(codigo_hash) and secrets.compare_digest(sha256(codigo), codigo_hash)
