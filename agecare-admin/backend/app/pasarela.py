"""Cliente de la Pasarela de pago (actor secundario en CU12 y CU15, primario en CU14).

Simulación: en producción estas funciones llamarían a la API del proveedor (p. ej. Webpay, Mercado Pago, Stripe).
Los webhooks entrantes se validan con una firma HMAC-SHA256 del cuerpo.
"""
import hashlib
import hmac
import secrets

from .config import get_settings


class PasarelaError(Exception):
    pass


def cancelar_suscripcion(id_externo: str | None) -> dict:
    return {"id": id_externo, "estado": "cancelada"}


def reembolsar(id_externo_transaccion: str | None, monto: int) -> dict:
    if monto <= 0:
        raise PasarelaError("Monto inválido")
    return {"id": f"re_{secrets.token_hex(8)}", "transaccion": id_externo_transaccion, "monto": monto, "estado": "procesado"}


def firmar(cuerpo: bytes) -> str:
    return hmac.new(get_settings().pasarela_webhook_secret.encode(), cuerpo, hashlib.sha256).hexdigest()


def firma_valida(cuerpo: bytes, firma: str | None) -> bool:
    return bool(firma) and hmac.compare_digest(firmar(cuerpo), firma)
