"""Actor «Planificador de tareas»: ejecuta los jobs programados en un hilo de la API.

Cada ciclo (60 s por defecto): CU27/CU28 monitoreo de componentes, publicación de contenido programado y
CU42 envío y reintento de los avisos por WhatsApp pendientes.
Cada hora: cierre automático de tickets resueltos (7 días) y CU26 consolidación de métricas de soporte.
En Render (plan gratuito) corre dentro de la misma API; si el servicio se suspende por inactividad, se retoma al despertar.
"""
import logging
import threading
import time
from datetime import timedelta

from sqlalchemy import select

from .audit import registrar
from .config import get_settings
from .db import SessionLocal, utcnow
from .metricas_job import consolidar_soporte
from .models import ParametroSistema, Ticket
from .monitor import ejecutar_ciclo
from .whatsapp import procesar_pendientes as procesar_whatsapp

log = logging.getLogger("planificador")
_stop = threading.Event()


def cerrar_tickets_resueltos(db) -> int:
    p = db.get(ParametroSistema, "dias_cierre_automatico_tickets")
    dias = int(float(p.valor)) if p else 7
    limite = utcnow() - timedelta(days=dias)
    tickets = db.scalars(select(Ticket).where(Ticket.estado == "resuelto", Ticket.fecha_resolucion <= limite)).all()
    for t in tickets:
        t.estado, t.fecha_cierre = "cerrado", utcnow()
        registrar(db, actor=None, accion="ticket.cierre_automatico", tipo_entidad="ticket", id_entidad=t.id_ticket,
                  antes={"estado": "resuelto"}, despues={"estado": "cerrado"})
    db.commit()
    return len(tickets)


def tick(n: int) -> None:
    from .routers.contenido import publicar_programados
    with SessionLocal() as db:
        ejecutar_ciclo(db)
        publicar_programados(db)
        procesar_whatsapp(db)
        if n % 60 == 0:
            cerrar_tickets_resueltos(db)
            consolidar_soporte(db)
            db.commit()


def _resumen(exc: BaseException) -> str:
    """Una sola línea legible: tipo y primera línea del mensaje (sin traza ni SQL)."""
    msg = (str(getattr(exc, "orig", None) or exc).strip().splitlines() or [""])[0]
    return f"{type(exc).__name__}: {msg[:200]}"


class _Fallos:
    """DEF-10: con la BD caída se registraba la traza completa cada minuto. Ahora se escribe una línea al fallar,
    un recordatorio cada 10 ciclos seguidos y una línea al recuperarse. La traza solo sale con LOG_LEVEL=DEBUG."""

    def __init__(self) -> None:
        self.seguidos = 0

    def fallo(self, exc: BaseException) -> None:
        self.seguidos += 1
        if self.seguidos == 1 or self.seguidos % 10 == 0:
            log.error("ciclo fallido (%s seguidos): %s", self.seguidos, _resumen(exc))
        log.debug("traza del ciclo fallido", exc_info=exc)

    def ok(self) -> None:
        if self.seguidos:
            log.warning("planificador recuperado tras %s ciclos fallidos", self.seguidos)
        self.seguidos = 0


def _loop(intervalo: int) -> None:
    n, fallos = 0, _Fallos()
    while not _stop.wait(intervalo if n else 5):
        try:
            tick(n)
            fallos.ok()
        except Exception as exc:  # el planificador nunca debe botar la API
            fallos.fallo(exc)
        n += 1


def iniciar() -> None:
    intervalo = get_settings().planificador_intervalo_seg
    if intervalo > 0:
        _stop.clear()
        threading.Thread(target=_loop, args=(intervalo,), daemon=True, name="planificador").start()


def detener() -> None:
    _stop.set()
