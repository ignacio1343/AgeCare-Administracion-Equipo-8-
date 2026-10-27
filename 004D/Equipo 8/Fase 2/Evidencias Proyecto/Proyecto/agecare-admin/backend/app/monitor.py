"""CU27 Monitorear componentes · CU28 Abrir incidente automático.

En producción el Planificador ejecuta un ciclo cada 60 s haciendo health checks reales a cada componente de la
Plataforma AgeCare. Aquí la base de datos se verifica de verdad y el resto de componentes se simula con
latencias realistas; `simular_falla` permite forzar la caída de un componente para la demo.
"""
import random
import time
from datetime import timedelta

from sqlalchemy import case, func, select, text
from sqlalchemy.orm import Session

from .audit import registrar
from .db import utcnow
from .models import Componente, ComponenteProceso, Incidente, ProcesoCritico, VerificacionSalud

FALLOS_PARA_CAIDA = 3
BASE_LATENCIA = {"api_core": 90, "database": 8, "auth": 120, "push": 1800, "alert_engine": 240, "wearable_ingest": 110,
                 "ai_assistant": 2100, "storage": 130, "music_sync": 150}


def _check(db: Session, c: Componente, rnd: random.Random, simular_falla: set[str]) -> tuple[bool, int | None, str | None]:
    if c.codigo_componente in simular_falla:
        return False, None, "Sin respuesta (falla simulada)"
    if c.codigo_componente == "database":
        t0 = time.perf_counter()
        db.execute(text("SELECT 1"))
        return True, max(1, int((time.perf_counter() - t0) * 1000)), None
    base = BASE_LATENCIA.get(c.codigo_componente, 150)
    lat = int(rnd.lognormvariate(0, 0.35) * base)
    return True, lat, None


def _percentil(vals: list[int], p: float) -> int | None:
    if not vals:
        return None
    vals = sorted(vals)
    return vals[min(len(vals) - 1, int(round(p * (len(vals) - 1))))]


def ejecutar_ciclo(db: Session, simular_falla: set[str] | None = None, rnd: random.Random | None = None) -> list[Incidente]:
    rnd = rnd or random.Random()
    simular_falla = simular_falla or set()
    now = utcnow()
    abiertos: list[Incidente] = []
    for c in db.scalars(select(Componente).order_by(Componente.orden)):
        ok, lat, detalle = _check(db, c, rnd, simular_falla)
        db.add(VerificacionSalud(codigo_componente=c.codigo_componente, fecha_hora=now, exitosa=ok, latencia_ms=lat,
                                 detalle=detalle))
        db.flush()
        recientes = db.scalars(select(VerificacionSalud.latencia_ms).where(
            VerificacionSalud.codigo_componente == c.codigo_componente, VerificacionSalud.exitosa.is_(True),
            VerificacionSalud.latencia_ms.is_not(None)).order_by(VerificacionSalud.fecha_hora.desc()).limit(60)).all()
        c.latencia_p50_ms, c.latencia_p95_ms = _percentil(list(recientes), .5), _percentil(list(recientes), .95)
        total, buenos = db.execute(select(func.count(), func.sum(case((VerificacionSalud.exitosa.is_(True), 1), else_=0)))
                                   .where(VerificacionSalud.codigo_componente == c.codigo_componente,
                                          VerificacionSalud.fecha_hora >= now - timedelta(days=30))).one()
        c.uptime_30d = round((buenos or 0) / total, 5) if total else 1

        anterior = c.estado_actual
        c.fallos_consecutivos = 0 if ok else c.fallos_consecutivos + 1
        if c.fallos_consecutivos >= FALLOS_PARA_CAIDA:
            nuevo = "caido"
        elif ok and c.latencia_p95_ms and c.latencia_p95_ms > c.umbral_p95_ms:
            nuevo = "degradado"
        elif ok:
            nuevo = "operativo"
        else:
            nuevo = anterior
        if nuevo != anterior:
            c.estado_actual, c.estado_desde = nuevo, now
            registrar(db, actor=None, accion="operacion.cambio_estado", tipo_entidad="componente",
                      id_entidad=c.codigo_componente, antes={"estado": anterior}, despues={"estado": nuevo})
        if nuevo == "caido" and anterior != "caido":
            ya = db.scalar(select(Incidente).where(Incidente.codigo_componente == c.codigo_componente,
                                                   Incidente.estado.in_(("investigando", "en_observacion"))))
            if ya is None:
                inc = Incidente(codigo_componente=c.codigo_componente, titulo=f"{c.nombre} no responde",
                                severidad="caido", estado="investigando", creado_automaticamente=True,
                                descripcion=f"Apertura automática: {FALLOS_PARA_CAIDA} verificaciones fallidas seguidas.",
                                fecha_inicio=now)
                db.add(inc)
                db.flush()
                registrar(db, actor=None, accion="incidente.abrir_automatico", tipo_entidad="incidente",
                          id_entidad=inc.id_incidente, despues={"componente": c.codigo_componente})
                abiertos.append(inc)  # aquí se notificaría al staff (correo/push)
    # Estado de los procesos críticos = peor estado de sus componentes
    orden = {"operativo": 0, "degradado": 1, "caido": 2}
    estados = {c.codigo_componente: c.estado_actual for c in db.scalars(select(Componente))}
    for p in db.scalars(select(ProcesoCritico)):
        comps = db.scalars(select(ComponenteProceso.codigo_componente)
                           .where(ComponenteProceso.codigo_proceso == p.codigo_proceso)).all()
        p.estado = max((estados.get(x, "operativo") for x in comps), key=lambda s: orden[s], default="operativo")
    db.commit()
    return abiertos
