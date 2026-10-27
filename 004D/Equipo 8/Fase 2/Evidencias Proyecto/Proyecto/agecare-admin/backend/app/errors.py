"""Formato estándar de error (spec 2.4): {"error": {code, message, details, request_id}}."""
import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, details=None, headers: dict | None = None):
        self.status, self.code, self.message, self.details, self.headers = status, code, message, details, headers


def _body(code: str, message: str, details, request: Request) -> dict:
    rid = getattr(request.state, "request_id", None) or str(uuid.uuid4())
    return {"error": {"code": code, "message": message, "details": details, "request_id": rid}}


COMMON = {
    401: ("UNAUTHORIZED", "Tu sesión de administración expiró. Vuelve a iniciar sesión."),
    403: ("FORBIDDEN", "Tu rol no tiene permisos sobre este módulo."),
    404: ("NOT_FOUND", "El recurso solicitado no existe."),
    405: ("METHOD_NOT_ALLOWED", "Método no permitido."),
    429: ("RATE_LIMITED", "Demasiadas solicitudes. Intenta de nuevo en unos segundos."),
}


log_acceso = logging.getLogger("acceso")
log_error = logging.getLogger("errores")
LENTO_MS = 1000  # peticiones sobre 1 s se registran como WARNING para encontrarlas rápido en los logs


def install(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_id(request: Request, call_next):
        request.state.request_id = str(uuid.uuid4())
        t0 = time.perf_counter()
        response = await call_next(request)
        ms = (time.perf_counter() - t0) * 1000
        response.headers["X-Request-ID"] = request.state.request_id
        # Una línea por petición (método, ruta, estado, duración, request_id). Sin query string ni cuerpo:
        # así nunca quedan tokens ni datos personales en los logs. El health check de Render no se registra.
        if not request.url.path.endswith("/health"):
            nivel = logging.WARNING if ms >= LENTO_MS or response.status_code >= 500 else logging.INFO
            log_acceso.log(nivel, "%s %s %s %.0fms rid=%s", request.method, request.url.path, response.status_code, ms,
                           request.state.request_id)
        return response

    @app.exception_handler(ApiError)
    async def api_error(request: Request, exc: ApiError):
        return JSONResponse(_body(exc.code, exc.message, exc.details, request), status_code=exc.status, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        details = [{"field": ".".join(str(p) for p in e["loc"][1:]) or e["loc"][0], "message": e["msg"]} for e in exc.errors()]
        return JSONResponse(_body("VALIDATION_ERROR", "Hay datos inválidos en la solicitud. Revisa los campos marcados.",
                                  details, request), status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        code, message = COMMON.get(exc.status_code, ("HTTP_ERROR", str(exc.detail)))
        return JSONResponse(_body(code, message, None, request), status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):  # pragma: no cover
        rid = getattr(request.state, "request_id", None)
        log_error.error("error no controlado en %s %s rid=%s", request.method, request.url.path, rid, exc_info=exc)
        return JSONResponse(_body("INTERNAL_ERROR", "Error interno. Revisa el request_id en los logs.", None, request),
                            status_code=500)
