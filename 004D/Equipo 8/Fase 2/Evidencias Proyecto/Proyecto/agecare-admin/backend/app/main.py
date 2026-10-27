"""AgeCare · Consola de Administración — API (Avance 2)."""
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text
from fastapi.middleware.cors import CORSMiddleware

from . import errors, planificador
from .config import get_settings
from .db import SessionLocal
from .errors import ApiError
from .routers import (auth, comercial, configuracion, contenido, metricas, moderacion, operacion, soporte, staff,
                      usuarios, whatsapp)

API = "/api/v1"

# Registros técnicos en la salida estándar (Render los muestra en Logs y permite buscarlos por request_id)
logging.basicConfig(level=get_settings().log_level.upper(), format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                    force=True)
logging.getLogger("uvicorn.access").disabled = True  # reemplazado por el registro «acceso» (incluye duración y rid)

@asynccontextmanager
async def lifespan(_app):
    planificador.iniciar()
    yield
    planificador.detener()


app = FastAPI(
    lifespan=lifespan,
    title="AgeCare · API de la Consola de Administración",
    version="0.5.1",
    description="Consola de administración AgeCare: acceso y auditoría, soporte, usuarios de la app, estado operativo, contenidos, moderación, dashboards, planes y suscripciones, configuración y legales, y avisos de salud por WhatsApp al familiar.",
    docs_url=f"{API}/docs", openapi_url=f"{API}/openapi.json", redoc_url=None,
)
errors.install(app)
app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_list, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"], expose_headers=["X-Request-ID"])

for r in (auth.router, staff.router, soporte.router, usuarios.router, operacion.router, contenido.router,
          moderacion.router, metricas.router, comercial.router, configuracion.router, whatsapp.router):
    app.include_router(r, prefix=API)


@app.get(f"{API}/health", tags=["Sistema"])
def health():
    """Usado por el health check de Render: no toca la BD, así no despierta a Neon cada pocos segundos."""
    return {"status": "ok", "version": app.version}


@app.get(f"{API}/health/db", tags=["Sistema"], summary="Estado de la base de datos (diagnóstico)")
def health_db():
    t0 = time.perf_counter()
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except Exception as exc:
        logging.getLogger("errores").error("health/db sin conexión: %s", type(exc).__name__)
        raise ApiError(503, "DB_UNAVAILABLE", "La base de datos no responde.") from None
    return {"status": "ok", "db_ms": round((time.perf_counter() - t0) * 1000, 1)}


@app.get("/", include_in_schema=False)
def raiz():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(f"{API}/docs")
