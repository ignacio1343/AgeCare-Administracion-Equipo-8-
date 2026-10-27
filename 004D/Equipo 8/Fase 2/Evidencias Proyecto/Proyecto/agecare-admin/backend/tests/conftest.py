"""Pruebas: por defecto usan SQLite (no requieren servidor). Para correrlas sobre PostgreSQL:
    TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/agecare_test pytest
"""
import os

os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", "sqlite:///./test_agecare.db")
os.environ["PLANIFICADOR_INTERVALO_SEG"] = "0"
os.environ["COOKIE_SECURE"] = "false"  # el cliente de pruebas usa http://testserver

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.catalogos import cargar_catalogos  # noqa: E402
from app.db import Base, SessionLocal, engine, utcnow  # noqa: E402
from app.main import app  # noqa: E402
from app.models import MiembroStaff, UsuarioApp  # noqa: E402
from app.security import hash_password  # noqa: E402

API = "/api/v1"
PWD = "Clave1234"
CUENTAS = {"admin": "admin@wellq.co.uk", "soporte": "soporte@wellq.co.uk", "analista": "analista@wellq.co.uk",
           "editor": "editora@wellq.co.uk", "moderador": "moderador@wellq.co.uk"}


@pytest.fixture(autouse=True)
def db_limpia():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        cargar_catalogos(db)
        for rol, email in CUENTAS.items():
            db.add(MiembroStaff(nombre_completo=f"{rol.title()} Prueba", email=email, codigo_rol=rol, estado="activo",
                                password_hash=hash_password(PWD), fecha_activacion=utcnow()))
        db.add(UsuarioApp(nombre="Ana Pérez", email="ana@example.com"))
        db.commit()
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


RH = {"X-ACA-Refresh": "1"}  # cabecera anti-CSRF de /auth/refresh y /auth/logout


def con_cookie(client, token):
    """Deja en el cliente solo la cookie de refresh indicada (simula un navegador con ese token)."""
    client.cookies.clear()
    if token:
        client.cookies.set("aca_refresh", token, path="/api/v1/auth")


def login(client, rol="admin", password=PWD, **extra):
    return client.post(f"{API}/auth/login", json={"email": CUENTAS.get(rol, rol), "password": password, **extra})


@pytest.fixture
def auth(client):
    """auth("soporte") -> headers con el access token de ese rol."""
    def _h(rol="admin"):
        r = login(client, rol)
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['access_token']}"}
    return _h
