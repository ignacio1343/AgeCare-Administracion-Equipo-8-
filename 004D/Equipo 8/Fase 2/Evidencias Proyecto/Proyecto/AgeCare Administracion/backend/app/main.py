"""AgeCare · Consola de Administración — API (Avance 2)."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import errors
from .config import get_settings
from .routers import auth, staff

API = "/api/v1"

app = FastAPI(
    title="AgeCare · API de la Consola de Administración",
    version="0.3.0",
    description="Consola de administración AgeCare: acceso y auditoría, soporte, usuarios de la app, estado operativo, contenidos, moderación, dashboards, planes y suscripciones, configuración y legales.",
    docs_url=f"{API}/docs", openapi_url=f"{API}/openapi.json", redoc_url=None,
)
errors.install(app)
app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_list, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"], expose_headers=["X-Request-ID"])

for r in (auth.router, staff.router,):
    app.include_router(r, prefix=API)


@app.get(f"{API}/health", tags=["Sistema"])
def health():
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def raiz():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(f"{API}/docs")
