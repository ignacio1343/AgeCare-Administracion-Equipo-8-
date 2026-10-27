"""Jobs del Planificador de tareas, para ejecutarlos a mano o desde cron.

Uso:  python -m scripts.jobs cerrar-tickets | monitor | consolidar
(La API ya los ejecuta sola en segundo plano; ver app/planificador.py)
"""
import sys

from app.db import SessionLocal
from app.metricas_job import consolidar
from app.monitor import ejecutar_ciclo
from app.planificador import cerrar_tickets_resueltos

if __name__ == "__main__":
    cmd = sys.argv[1:2]
    with SessionLocal() as db:
        if cmd == ["cerrar-tickets"]:
            print(f"Tickets cerrados: {cerrar_tickets_resueltos(db)}")
        elif cmd == ["monitor"]:
            print(f"Incidentes abiertos automáticamente: {len(ejecutar_ciclo(db))}")
        elif cmd == ["consolidar"]:
            print(consolidar(db))
            db.commit()
        else:
            print(__doc__)
