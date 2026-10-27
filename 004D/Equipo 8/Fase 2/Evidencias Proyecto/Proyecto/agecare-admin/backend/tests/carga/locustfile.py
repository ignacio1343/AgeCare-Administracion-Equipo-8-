"""Prueba de carga (EP10-HU07 · CP-19) sobre los endpoints críticos de la consola.

Local:   locust -f tests/carga/locustfile.py --host http://localhost:8000 --headless -u 50 -r 5 -t 2m --csv carga
Render:  workflow «Prueba de carga» de GitHub Actions (usa la URL pública) o el mismo comando con --host <URL>.
Criterio (RNF-08): p95 < 800 ms en las consultas con 50 usuarios simultáneos y 0 % de errores.
"""
import os

from locust import HttpUser, between, task

EMAIL = os.environ.get("CARGA_EMAIL", "analista@wellq.co.uk")
PASSWORD = os.environ.get("CARGA_PASSWORD", "Analista123!")


class Staff(HttpUser):
    wait_time = between(1, 2)

    def on_start(self):
        r = self.client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD}, name="POST /auth/login")
        self.h = {"Authorization": "Bearer " + r.json()["access_token"]} if r.ok else {}

    @task(3)
    def cola(self):
        self.client.get("/api/v1/soporte/tickets?activos=true&page_size=15", headers=self.h, name="GET /soporte/tickets")

    @task(2)
    def indicadores(self):
        self.client.get("/api/v1/soporte/indicadores", headers=self.h, name="GET /soporte/indicadores")

    @task(2)
    def estado(self):
        self.client.get("/api/v1/operacion/estado", headers=self.h, name="GET /operacion/estado")

    @task(2)
    def comerciales(self):
        self.client.get("/api/v1/metricas/comerciales?periodo=30d", headers=self.h, name="GET /metricas/comerciales")

    @task(1)
    def adopcion(self):
        self.client.get("/api/v1/metricas/adopcion?ventana=30", headers=self.h, name="GET /metricas/adopcion")

    @task(1)
    def transacciones(self):
        self.client.get("/api/v1/comercial/transacciones?page_size=25", headers=self.h, name="GET /comercial/transacciones")
