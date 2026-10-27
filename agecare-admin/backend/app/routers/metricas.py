"""Dashboards y estadísticas: CU21 Métricas comerciales · CU22 Embudo de conversión · CU23 Métricas por perfil
· CU24 Adopción de funcionalidades · CU26 Consolidar métricas agregadas."""
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..audit import registrar
from ..db import get_db, hoy_local
from ..deps import requiere
from ..metricas_job import consolidar
from ..models import (ActividadPerfil, AdopcionFuncionalidad, Funcionalidad, MetricaDiaria, MetricaSoporteDiaria,
                      MiembroStaff, PerfilApp, Plan, SnapshotEmbudo, SnapshotPlan)

router = APIRouter(prefix="/metricas", tags=["Dashboards"])
LECTURA, ESCRITURA = requiere("metricas", "lectura"), requiere("metricas", "escritura")
Periodo = Literal["7d", "30d", "mes", "ytd", "12m"]
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sept", "oct", "nov", "dic"]


class Kpi(BaseModel):
    valor: float
    anterior: float | None
    variacion: float | None


class ComercialOut(BaseModel):
    periodo: str
    desde: date
    hasta: date
    descargas: Kpi
    altas: Kpi
    bajas: Kpi
    usuarios_activos: Kpi
    usuarios_pago: Kpi
    mrr: Kpi
    churn_periodo: float
    serie_etiquetas: list[str]
    serie_altas: list[int]
    serie_bajas: list[int]
    actualizado: date | None


class PlanMix(BaseModel):
    codigo_plan: str
    nombre: str
    unidad_facturable: str
    usuarios: int
    cuota: float
    precio: int | None
    mrr: int
    churn_mensual: float


class PlanesOut(BaseModel):
    fecha: date | None
    planes: list[PlanMix]
    total_usuarios: int
    total_mrr: int


class EmbudoPaso(BaseModel):
    etapa: str
    valor: int
    sobre_descargas: float
    sobre_anterior: float | None


class EmbudoOut(BaseModel):
    fecha: date | None
    pasos: list[EmbudoPaso]
    conversion_pago: float
    conversion_pago_hace_30d: float | None


class PerfilOut(BaseModel):
    codigo_perfil: str
    nombre: str
    usuarios_activos: int
    sesiones_semana: float
    duracion_media_seg: int
    retencion_30d: float


class Celda(BaseModel):
    codigo_perfil: str
    adopcion: float | None
    usuarios: int | None


class FilaAdopcion(BaseModel):
    codigo_funcionalidad: str
    nombre: str
    uso_bajo_esperado: bool
    nota: str | None
    celdas: list[Celda]


class AlertaAdopcion(BaseModel):
    funcionalidad: str
    perfil: str
    adopcion: float


class AdopcionOut(BaseModel):
    ventana_dias: int
    perfiles: list[dict]
    filas: list[FilaAdopcion]
    alertas: list[AlertaAdopcion]


class SoporteSerieOut(BaseModel):
    fechas: list[date]
    creados: list[int]
    resueltos: list[int]
    primera_respuesta_h: list[float | None]
    csat: list[float | None]


def _rango(periodo: str, hoy: date) -> tuple[date, date]:
    if periodo == "7d":
        return hoy - timedelta(days=6), hoy
    if periodo == "30d":
        return hoy - timedelta(days=29), hoy
    if periodo == "mes":
        return hoy.replace(day=1), hoy
    if periodo == "ytd":
        return hoy.replace(month=1, day=1), hoy
    return (hoy.replace(day=1) - timedelta(days=335)).replace(day=1), hoy


def _kpi(v: float, a: float | None) -> Kpi:
    var = round((v - a) / a, 4) if a else None
    return Kpi(valor=v, anterior=a, variacion=var)


@router.get("/comerciales", response_model=ComercialOut, summary="CU21 · Métricas comerciales por periodo")
def comerciales(periodo: Periodo = "mes", _: MiembroStaff = Depends(LECTURA), db: Session = Depends(get_db)):
    hoy = db.scalar(select(func.max(MetricaDiaria.fecha))) or hoy_local()
    desde, hasta = _rango(periodo, hoy)
    dias = (hasta - desde).days + 1
    p_desde, p_hasta = desde - timedelta(days=dias), desde - timedelta(days=1)
    rows = db.scalars(select(MetricaDiaria).where(MetricaDiaria.fecha.between(desde, hasta)).order_by(MetricaDiaria.fecha)).all()
    prev = db.scalars(select(MetricaDiaria).where(MetricaDiaria.fecha.between(p_desde, p_hasta))).all()
    suma = lambda rs, k: sum(getattr(r, k) for r in rs)  # noqa: E731
    ult = rows[-1] if rows else None
    ult_prev = max(prev, key=lambda r: r.fecha) if prev else None
    # serie: por día (≤ 31 días), por semana (≤ 92) o por mes
    etiquetas, altas, bajas = [], [], []
    if dias <= 31:
        for r in rows:
            etiquetas.append(f"{r.fecha.day} {MESES[r.fecha.month - 1]}")
            altas.append(r.altas)
            bajas.append(r.bajas)
    else:
        grupos: dict[tuple, list] = {}
        for r in rows:
            grupos.setdefault((r.fecha.year, r.fecha.month), []).append(r)
        for (y, m), rs in grupos.items():
            etiquetas.append(f"{MESES[m - 1]} {str(y)[2:]}")
            altas.append(suma(rs, "altas"))
            bajas.append(suma(rs, "bajas"))
    activos = ult.usuarios_activos if ult else 0
    return ComercialOut(
        periodo=periodo, desde=desde, hasta=hasta,
        descargas=_kpi(suma(rows, "descargas"), suma(prev, "descargas") or None),
        altas=_kpi(suma(rows, "altas"), suma(prev, "altas") or None),
        bajas=_kpi(suma(rows, "bajas"), suma(prev, "bajas") or None),
        usuarios_activos=_kpi(activos, ult_prev.usuarios_activos if ult_prev else None),
        usuarios_pago=_kpi(ult.usuarios_pago if ult else 0, ult_prev.usuarios_pago if ult_prev else None),
        mrr=_kpi(ult.mrr if ult else 0, ult_prev.mrr if ult_prev else None),
        churn_periodo=round(suma(rows, "bajas") / activos, 4) if activos else 0,
        serie_etiquetas=etiquetas, serie_altas=altas, serie_bajas=bajas, actualizado=ult.fecha if ult else None)


@router.get("/planes", response_model=PlanesOut, summary="CU21 · Mezcla de planes (último snapshot)")
def planes(_: MiembroStaff = Depends(LECTURA), db: Session = Depends(get_db)):
    f = db.scalar(select(func.max(SnapshotPlan.fecha)))
    if f is None:
        return PlanesOut(fecha=None, planes=[], total_usuarios=0, total_mrr=0)
    rows = db.execute(select(SnapshotPlan, Plan).join(Plan).where(SnapshotPlan.fecha == f).order_by(Plan.orden)).all()
    total = sum(s.usuarios for s, _ in rows) or 1
    return PlanesOut(fecha=f, total_usuarios=sum(s.usuarios for s, _ in rows), total_mrr=sum(s.mrr for s, _ in rows),
                     planes=[PlanMix(codigo_plan=p.codigo_plan, nombre=p.nombre, unidad_facturable=p.unidad_facturable,
                                     usuarios=s.usuarios, cuota=round(s.usuarios / total, 4), precio=s.precio_congelado,
                                     mrr=s.mrr, churn_mensual=float(s.churn_mensual)) for s, p in rows])


@router.get("/embudo", response_model=EmbudoOut, summary="CU22 · Embudo de conversión freemium")
def embudo(_: MiembroStaff = Depends(LECTURA), db: Session = Depends(get_db)):
    e = db.scalar(select(SnapshotEmbudo).order_by(SnapshotEmbudo.fecha.desc()).limit(1))
    if e is None:
        return EmbudoOut(fecha=None, pasos=[], conversion_pago=0, conversion_pago_hace_30d=None)
    antes = db.scalar(select(SnapshotEmbudo).where(SnapshotEmbudo.fecha <= e.fecha - timedelta(days=30))
                      .order_by(SnapshotEmbudo.fecha.desc()).limit(1))
    etapas = [("Descargas", e.descargas), ("Cuentas creadas", e.cuentas_creadas), ("Activos últimos 30 d", e.activos_30d),
              ("En plan de pago", e.de_pago)]
    pasos = [EmbudoPaso(etapa=n, valor=v, sobre_descargas=round(v / e.descargas, 4) if e.descargas else 0,
                        sobre_anterior=round(v / etapas[i - 1][1], 4) if i and etapas[i - 1][1] else None)
             for i, (n, v) in enumerate(etapas)]
    conv = lambda s: round(s.de_pago / s.activos_30d, 4) if s and s.activos_30d else None  # noqa: E731
    return EmbudoOut(fecha=e.fecha, pasos=pasos, conversion_pago=conv(e) or 0, conversion_pago_hace_30d=conv(antes))


@router.get("/perfiles", response_model=list[PerfilOut], summary="CU23 · Métricas por perfil de usuario")
def perfiles(ventana: int = Query(30), _: MiembroStaff = Depends(LECTURA), db: Session = Depends(get_db)):
    rows = db.execute(select(ActividadPerfil, PerfilApp).join(PerfilApp).where(ActividadPerfil.ventana_dias == ventana)
                      .order_by(ActividadPerfil.usuarios_activos.desc())).all()
    return [PerfilOut(codigo_perfil=p.codigo_perfil, nombre=p.nombre, usuarios_activos=a.usuarios_activos,
                      sesiones_semana=float(a.sesiones_semana), duracion_media_seg=a.duracion_media_seg,
                      retencion_30d=float(a.retencion_30d)) for a, p in rows]


@router.get("/adopcion", response_model=AdopcionOut, summary="CU24 · Adopción de funcionalidades por perfil")
def adopcion(ventana: int = Query(30), umbral_alerta: float = Query(0.15, ge=0, le=1),
             _: MiembroStaff = Depends(LECTURA), db: Session = Depends(get_db)):
    perfiles_ = db.scalars(select(PerfilApp).order_by(PerfilApp.codigo_perfil)).all()
    orden = ["familiar", "cuidadora", "adulto_mayor", "medico"]
    perfiles_.sort(key=lambda p: orden.index(p.codigo_perfil) if p.codigo_perfil in orden else 99)
    datos = {(a.codigo_funcionalidad, a.codigo_perfil): a for a in
             db.scalars(select(AdopcionFuncionalidad).where(AdopcionFuncionalidad.ventana_dias == ventana))}
    filas, alertas = [], []
    for f in db.scalars(select(Funcionalidad).order_by(Funcionalidad.orden)):
        celdas = []
        for p in perfiles_:
            a = datos.get((f.codigo_funcionalidad, p.codigo_perfil))
            celdas.append(Celda(codigo_perfil=p.codigo_perfil, adopcion=float(a.adopcion) if a else None,
                                usuarios=a.usuarios if a else None))
            if a and float(a.adopcion) < umbral_alerta and not f.uso_bajo_esperado:
                alertas.append(AlertaAdopcion(funcionalidad=f.nombre, perfil=p.nombre, adopcion=float(a.adopcion)))
        filas.append(FilaAdopcion(codigo_funcionalidad=f.codigo_funcionalidad, nombre=f.nombre,
                                  uso_bajo_esperado=f.uso_bajo_esperado, nota=f.nota, celdas=celdas))
    alertas.sort(key=lambda x: x.adopcion)
    return AdopcionOut(ventana_dias=ventana, perfiles=[{"codigo": p.codigo_perfil, "nombre": p.nombre} for p in perfiles_],
                       filas=filas, alertas=alertas)


@router.get("/soporte", response_model=SoporteSerieOut, summary="Serie diaria de soporte (seguimiento de OE1)")
def soporte(dias: int = Query(30, ge=7, le=365), _: MiembroStaff = Depends(LECTURA), db: Session = Depends(get_db)):
    rows = db.scalars(select(MetricaSoporteDiaria).order_by(MetricaSoporteDiaria.fecha.desc()).limit(dias)).all()[::-1]
    n = lambda v: float(v) if v is not None else None  # noqa: E731
    return SoporteSerieOut(fechas=[r.fecha for r in rows], creados=[r.tickets_creados for r in rows],
                           resueltos=[r.tickets_resueltos for r in rows],
                           primera_respuesta_h=[n(r.t_primera_respuesta_prom) for r in rows],
                           csat=[n(r.csat_promedio) for r in rows])


@router.post("/consolidar", summary="CU26 · Consolidar métricas agregadas ahora (lo hace el Planificador cada noche)")
def consolidar_ahora(request: Request, staff: MiembroStaff = Depends(ESCRITURA), db: Session = Depends(get_db)):
    res = consolidar(db)
    registrar(db, actor=staff, accion="metricas.consolidar", tipo_entidad="metricas", despues=res, request=request)
    db.commit()
    return res
