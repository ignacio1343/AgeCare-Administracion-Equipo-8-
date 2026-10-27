"""CU26 Consolidar métricas agregadas (actor: Planificador de tareas).

- METRICA_SOPORTE_DIARIA se calcula desde los tickets de esta misma base (datos propios de la consola).
- Se informa el conteo de suscripciones vigentes por plan de las cuentas gestionadas en la consola.
- Las demás tablas (métrica diaria, snapshot de planes, embudo, perfiles, adopción) se alimentan, en producción,
  desde la base de la Plataforma AgeCare y las tiendas de apps; en esta versión las carga el seed con datos simulados.
"""
from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .db import hoy_local, utcnow
from .models import EncuestaSatisfaccion, MetricaSoporteDiaria, Plan, SnapshotPlan, Suscripcion, Ticket


def _dia(dt) -> date:
    """Día de negocio (zona horaria configurada) de una marca de tiempo UTC."""
    from zoneinfo import ZoneInfo
    from .config import get_settings
    return dt.astimezone(ZoneInfo(get_settings().zona_horaria)).date()


def consolidar_soporte(db: Session, dias: int = 60) -> int:
    hoy = hoy_local()
    desde = hoy - timedelta(days=dias - 1)
    creados, resueltos, primera, resol, csat = (defaultdict(int), defaultdict(int), defaultdict(list),
                                                defaultdict(list), defaultdict(list))
    for t in db.scalars(select(Ticket)):
        dc = _dia(t.fecha_creacion)
        if dc >= desde:
            creados[dc] += 1
            if t.fecha_primera_respuesta:
                primera[dc].append((t.fecha_primera_respuesta - t.fecha_creacion).total_seconds() / 3600)
        if t.fecha_resolucion and _dia(t.fecha_resolucion) >= desde:
            dr = _dia(t.fecha_resolucion)
            resueltos[dr] += 1
            resol[dr].append((t.fecha_resolucion - t.fecha_creacion).total_seconds() / 3600)
    for e in db.scalars(select(EncuestaSatisfaccion).where(EncuestaSatisfaccion.puntaje.is_not(None))):
        if e.fecha_respuesta and _dia(e.fecha_respuesta) >= desde:
            csat[_dia(e.fecha_respuesta)].append(e.puntaje)
    db.execute(delete(MetricaSoporteDiaria).where(MetricaSoporteDiaria.fecha >= desde))
    prom = lambda xs: round(sum(xs) / len(xs), 2) if xs else None  # noqa: E731
    n = 0
    d = desde
    while d <= hoy:
        db.add(MetricaSoporteDiaria(fecha=d, tickets_creados=creados[d], tickets_resueltos=resueltos[d],
                                    t_primera_respuesta_prom=prom(primera[d]), t_resolucion_prom=prom(resol[d]),
                                    csat_promedio=prom(csat[d])))
        d += timedelta(days=1)
        n += 1
    return n


def consolidar_planes_cuentas(db: Session) -> dict:
    """Resumen de suscripciones vigentes por plan (cuentas gestionadas en la consola)."""
    conteo: dict[str, int] = defaultdict(int)
    for s in db.scalars(select(Suscripcion).where(Suscripcion.estado.in_(("activa", "en_mora")))):
        conteo[s.codigo_plan] += 1
    return dict(conteo)


def consolidar(db: Session) -> dict:
    dias = consolidar_soporte(db)
    db.flush()
    return {"metrica_soporte_diaria_dias": dias, "suscripciones_vigentes_por_plan": consolidar_planes_cuentas(db),
            "planes": [p.codigo_plan for p in db.scalars(select(Plan))], "snapshot_plan": "sin cambios (datos de plataforma)",
            "ultimo_snapshot_plan": str(db.scalar(select(SnapshotPlan.fecha).order_by(SnapshotPlan.fecha.desc()).limit(1)))}
