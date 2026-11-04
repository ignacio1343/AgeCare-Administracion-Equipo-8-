"""Pasarela de pago del portal: Transbank Webpay Plus (API REST v1.2).

Flujo
-----
1. `crear`: la API registra la transacción en Transbank y recibe un token y una URL.
2. El navegador del representante envía un formulario POST con `token_ws` a esa URL y paga en Webpay.
3. Webpay devuelve al navegador a `return_url` (nuestra API) con `token_ws` (pagado o rechazado), con `TBK_TOKEN`
   (el usuario anuló) o solo con `TBK_ORDEN_COMPRA` (se agotó el tiempo).
4. `confirmar` (commit): la API pregunta a Transbank el resultado. El pago solo es válido si `response_code == 0` y
   `status == "AUTHORIZED"`. El commit es obligatorio: sin él Transbank reversa el cargo.

Modos (`PAGOS_MODO`): «simulado» (página de pago de prueba propia, sin salir del portal) o «webpay».
En el entorno de integración se usan las credenciales públicas de Transbank y tarjetas de prueba
(VISA 4051 8856 0044 6623, CVV 123; RUT 11.111.111-1, clave 123).
"""
import json
import logging
import urllib.error
import urllib.request

from .config import get_settings

log = logging.getLogger("webpay")
HOSTS = {"integracion": "https://webpay3gint.transbank.cl", "produccion": "https://webpay3g.transbank.cl"}
RUTA = "/rswebpaytransaction/api/webpay/v1.2/transactions"
TIPOS_PAGO = {"VD": "Débito", "VN": "Crédito", "VC": "Crédito en cuotas", "SI": "3 cuotas sin interés",
              "S2": "2 cuotas sin interés", "NC": "N cuotas sin interés", "VP": "Prepago"}


class ErrorWebpay(Exception):
    pass


def modo() -> str:
    return "webpay" if get_settings().pagos_modo.lower() == "webpay" else "simulado"


def _host() -> str:
    return HOSTS.get(get_settings().webpay_entorno.lower(), HOSTS["integracion"])


def _llamar(metodo: str, ruta: str, cuerpo: dict | None = None) -> dict:
    st = get_settings()
    req = urllib.request.Request(_host() + ruta, method=metodo,
                                 data=json.dumps(cuerpo).encode() if cuerpo is not None else None,
                                 headers={"Tbk-Api-Key-Id": st.webpay_codigo_comercio,
                                          "Tbk-Api-Key-Secret": st.webpay_api_key,
                                          "Content-Type": "application/json"})
    try:
        # Host fijo de Transbank (HOSTS); no depende de datos del usuario
        with urllib.request.urlopen(req, timeout=15) as r:  # nosec B310
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            detalle = json.loads(e.read()).get("error_message", e.reason)
        except (ValueError, AttributeError):
            detalle = e.reason
        log.warning("Webpay %s %s respondió %s: %s", metodo, ruta.split("/")[-1][:12], e.code, detalle)
        raise ErrorWebpay(f"Transbank respondió {e.code}: {detalle}") from None
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        raise ErrorWebpay(f"No se pudo conectar con Transbank: {e}") from None


def crear(orden_compra: str, session_id: str, monto: int, return_url: str) -> dict:
    """Devuelve {"token": ..., "url": ...}."""
    return _llamar("POST", RUTA, {"buy_order": orden_compra, "session_id": session_id[:61], "amount": monto,
                                  "return_url": return_url})


def confirmar(token: str) -> dict:
    return _llamar("PUT", f"{RUTA}/{token}")


def estado(token: str) -> dict:
    return _llamar("GET", f"{RUTA}/{token}")


def aprobado(resp: dict) -> bool:
    return resp.get("response_code") == 0 and resp.get("status") == "AUTHORIZED"
