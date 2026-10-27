"""Simula a la pasarela de pagos enviando un webhook firmado a la API (CU14).

Uso:  python -m scripts.webhook_demo <id_suscripcion> [aprobado|rechazado] [monto]
Ej.:  python -m scripts.webhook_demo 4 aprobado 10000
La API debe estar corriendo en http://localhost:8000. Repetir el mismo evento no duplica nada (idempotencia).
"""
import json
import sys
import urllib.request
import uuid

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Suscripcion
from app.pasarela import firmar

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    id_sus = int(sys.argv[1])
    tipo = "pago.rechazado" if sys.argv[2:3] == ["rechazado"] else "pago.aprobado"
    with SessionLocal() as db:
        s = db.scalar(select(Suscripcion).where(Suscripcion.id_suscripcion == id_sus))
        if s is None or not s.id_externo_pasarela:
            sys.exit("Esa suscripción no existe o no tiene id en la pasarela.")
        monto = int(sys.argv[3]) if len(sys.argv) > 3 else s.plan.precio
        externo = s.id_externo_pasarela
    cuerpo = json.dumps({
        "id_evento": f"evt_{uuid.uuid4().hex[:12]}", "tipo": tipo, "id_suscripcion_externa": externo,
        "id_transaccion_externa": f"tx_{uuid.uuid4().hex[:12]}", "monto": monto, "medio_pago": "Visa ****4242",
        "codigo_error": "fondos_insuficientes" if tipo == "pago.rechazado" else None,
    }).encode()
    req = urllib.request.Request("http://localhost:8000/api/v1/pagos/webhook", data=cuerpo, method="POST",
                                 headers={"Content-Type": "application/json", "X-Pasarela-Firma": firmar(cuerpo)})
    with urllib.request.urlopen(req) as r:
        print(r.status, r.read().decode())
