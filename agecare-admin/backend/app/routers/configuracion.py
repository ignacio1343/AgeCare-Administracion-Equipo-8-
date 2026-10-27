"""Configuración, alertas y legales: CU05 Configurar umbrales de alertas · CU06 Configurar parámetros del sistema
· CU07 Gestionar documentos legales · CU08 Publicar versión legal."""
from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import registrar
from ..db import get_db, utcnow, hoy_local
from ..deps import requiere
from ..errors import ApiError
from ..models import MiembroStaff, ParametroSistema, TipoAlerta, UmbralAlerta, VersionLegal
from ..util import obtener

router = APIRouter(tags=["Configuración y legales"])
LECTURA, ESCRITURA = requiere("configuracion", "lectura"), requiere("configuracion", "escritura")


# ================================================================ CU06 parámetros
class ParametroOut(BaseModel):
    clave: str
    descripcion: str
    categoria: str
    tipo_valor: str
    valor: str
    version: int
    nota_cambio: str | None
    fecha_actualizacion: datetime | None


class ParametroIn(BaseModel):
    valor: str = Field(max_length=2000)
    version: int = Field(description="Versión que se editó (bloqueo optimista)")
    nota_cambio: str = Field(min_length=3, max_length=500)


def _valida(tipo: str, valor: str) -> str:
    v = valor.strip()
    if tipo == "numero":
        try:
            float(v.replace(",", "."))
        except ValueError:
            raise ApiError(422, "VALIDATION_ERROR", "El valor debe ser numérico.")
        return v.replace(",", ".")
    if tipo == "booleano":
        if v.lower() not in ("true", "false"):
            raise ApiError(422, "VALIDATION_ERROR", "El valor debe ser true o false.")
        return v.lower()
    if not v:
        raise ApiError(422, "VALIDATION_ERROR", "El valor no puede estar vacío.")
    return v


@router.get("/configuracion/parametros", response_model=list[ParametroOut], summary="Parámetros del sistema")
def parametros(_: MiembroStaff = Depends(LECTURA), db: Session = Depends(get_db)):
    return [ParametroOut.model_validate(p, from_attributes=True)
            for p in db.scalars(select(ParametroSistema).order_by(ParametroSistema.categoria, ParametroSistema.clave))]


@router.put("/configuracion/parametros/{clave}", response_model=ParametroOut, summary="CU06 · Cambiar un parámetro")
def editar_parametro(clave: str, data: ParametroIn, request: Request, staff: MiembroStaff = Depends(ESCRITURA),
                     db: Session = Depends(get_db)):
    p = obtener(db, ParametroSistema, clave, "El parámetro")
    if data.version != p.version:
        raise ApiError(409, "VERSION_CONFLICT", "Otra persona cambió este parámetro mientras lo editabas. Recarga y vuelve a intentar.",
                       {"version_actual": p.version, "valor_actual": p.valor})
    nuevo = _valida(p.tipo_valor, data.valor)
    if nuevo == p.valor:
        raise ApiError(409, "NO_CHANGE", "El valor es igual al actual.")
    antes = p.valor
    p.valor, p.version, p.nota_cambio, p.fecha_actualizacion = nuevo, p.version + 1, data.nota_cambio.strip(), utcnow()
    registrar(db, actor=staff, accion="configuracion.parametro", tipo_entidad="parametro_sistema", id_entidad=clave,
              antes={"valor": antes}, despues={"valor": nuevo, "version": p.version, "nota": p.nota_cambio}, request=request)
    db.commit()
    return ParametroOut.model_validate(p, from_attributes=True)


# ================================================================ CU05 umbrales
class UmbralOut(BaseModel):
    signo_vital: str
    nivel_semaforo: str
    codigo_tipo: str
    tipo_alerta: str
    valor_minimo: float
    valor_maximo: float
    unidad: str
    fecha_actualizacion: datetime | None


class UmbralIn(BaseModel):
    valor_minimo: float
    valor_maximo: float


def umbral_out(db: Session, u: UmbralAlerta) -> UmbralOut:
    t = db.get(TipoAlerta, u.codigo_tipo)
    return UmbralOut(signo_vital=u.signo_vital, nivel_semaforo=u.nivel_semaforo, codigo_tipo=u.codigo_tipo,
                     tipo_alerta=t.nombre if t else u.codigo_tipo, valor_minimo=float(u.valor_minimo),
                     valor_maximo=float(u.valor_maximo), unidad=u.unidad, fecha_actualizacion=u.fecha_actualizacion)


@router.get("/configuracion/umbrales", response_model=list[UmbralOut], summary="Umbrales de alertas por signo vital")
def umbrales(_: MiembroStaff = Depends(LECTURA), db: Session = Depends(get_db)):
    orden = {"verde": 0, "amarillo": 1, "rojo": 2}
    rows = sorted(db.scalars(select(UmbralAlerta)), key=lambda u: (u.signo_vital, orden.get(u.nivel_semaforo, 9)))
    return [umbral_out(db, u) for u in rows]


@router.put("/configuracion/umbrales/{signo_vital}/{nivel}", response_model=UmbralOut, summary="CU05 · Configurar umbral")
def editar_umbral(signo_vital: str, nivel: str, data: UmbralIn, request: Request, staff: MiembroStaff = Depends(ESCRITURA),
                  db: Session = Depends(get_db)):
    u = db.get(UmbralAlerta, (signo_vital, nivel))
    if u is None:
        raise ApiError(404, "NOT_FOUND", "El umbral no existe.")
    if data.valor_minimo > data.valor_maximo:
        raise ApiError(422, "INVALID_RANGE", "El mínimo no puede ser mayor que el máximo.")
    if data.valor_minimo < 0:
        raise ApiError(422, "INVALID_RANGE", "Los valores no pueden ser negativos.")
    antes = {"min": float(u.valor_minimo), "max": float(u.valor_maximo)}
    u.valor_minimo, u.valor_maximo, u.fecha_actualizacion = data.valor_minimo, data.valor_maximo, utcnow()
    registrar(db, actor=staff, accion="configuracion.umbral", tipo_entidad="umbral_alerta",
              id_entidad=f"{signo_vital}/{nivel}", antes=antes, despues={"min": data.valor_minimo, "max": data.valor_maximo},
              request=request)
    db.commit()
    return umbral_out(db, u)


# ================================================================ CU07 / CU08 legales
class VersionOut(BaseModel):
    id_version: int
    tipo_documento: str
    version: str
    contenido: str
    registro_cambios: str
    fecha_vigencia: date
    requiere_reaceptacion: bool
    estado: str
    autor: str
    fecha_publicacion: datetime | None


class VersionIn(BaseModel):
    tipo_documento: Literal["terminos", "privacidad"]
    contenido: str = Field(min_length=100, max_length=100_000)
    registro_cambios: str = Field(min_length=5, max_length=2000)
    fecha_vigencia: date
    cambio_mayor: bool = False


class VersionUpdateIn(BaseModel):
    contenido: str | None = Field(None, min_length=100, max_length=100_000)
    registro_cambios: str | None = Field(None, min_length=5, max_length=2000)
    fecha_vigencia: date | None = None


def version_out(v: VersionLegal) -> VersionOut:
    return VersionOut(id_version=v.id_version, tipo_documento=v.tipo_documento, version=f"{v.version_mayor}.{v.version_menor}",
                      contenido=v.contenido, registro_cambios=v.registro_cambios, fecha_vigencia=v.fecha_vigencia,
                      requiere_reaceptacion=v.requiere_reaceptacion, estado=v.estado, autor=v.autor.nombre_completo,
                      fecha_publicacion=v.fecha_publicacion)


@router.get("/legales/versiones", response_model=list[VersionOut], summary="Versiones de términos y privacidad")
def versiones(tipo: str | None = None, _: MiembroStaff = Depends(LECTURA), db: Session = Depends(get_db)):
    stmt = select(VersionLegal)
    if tipo:
        stmt = stmt.where(VersionLegal.tipo_documento == tipo)
    return [version_out(v) for v in db.scalars(stmt.order_by(VersionLegal.tipo_documento, VersionLegal.version_mayor.desc(),
                                                              VersionLegal.version_menor.desc()))]


@router.post("/legales/versiones", response_model=VersionOut, status_code=201, summary="CU07 · Redactar nueva versión")
def crear_version(data: VersionIn, request: Request, staff: MiembroStaff = Depends(ESCRITURA), db: Session = Depends(get_db)):
    if db.scalar(select(VersionLegal).where(VersionLegal.tipo_documento == data.tipo_documento,
                                            VersionLegal.estado == "borrador")):
        raise ApiError(409, "DRAFT_EXISTS", "Ya hay un borrador de este documento. Edítalo o publícalo primero.")
    ultima = db.scalar(select(VersionLegal).where(VersionLegal.tipo_documento == data.tipo_documento)
                       .order_by(VersionLegal.version_mayor.desc(), VersionLegal.version_menor.desc()).limit(1))
    if ultima is None:
        mayor, menor = 1, 0
    elif data.cambio_mayor:
        mayor, menor = ultima.version_mayor + 1, 0
    else:
        mayor, menor = ultima.version_mayor, ultima.version_menor + 1
    v = VersionLegal(id_staff_autor=staff.id_staff, tipo_documento=data.tipo_documento, version_mayor=mayor,
                     version_menor=menor, contenido=data.contenido, registro_cambios=data.registro_cambios.strip(),
                     fecha_vigencia=data.fecha_vigencia, requiere_reaceptacion=data.cambio_mayor, estado="borrador")
    db.add(v)
    db.flush()
    registrar(db, actor=staff, accion="legal.crear", tipo_entidad="version_legal", id_entidad=v.id_version,
              despues={"documento": v.tipo_documento, "version": f"{mayor}.{menor}"}, request=request)
    db.commit()
    db.refresh(v)
    return version_out(v)


@router.patch("/legales/versiones/{id_version}", response_model=VersionOut, summary="CU07 · Editar borrador")
def editar_version(id_version: int, data: VersionUpdateIn, request: Request, staff: MiembroStaff = Depends(ESCRITURA),
                   db: Session = Depends(get_db)):
    v = obtener(db, VersionLegal, id_version, "La versión")
    if v.estado != "borrador":
        raise ApiError(409, "PUBLISHED_IMMUTABLE", "Una versión publicada no se puede modificar; crea una nueva.")
    for k, val in data.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(v, k, val)
    registrar(db, actor=staff, accion="legal.editar", tipo_entidad="version_legal", id_entidad=v.id_version, request=request)
    db.commit()
    return version_out(v)


@router.post("/legales/versiones/{id_version}/publicar", response_model=VersionOut, summary="CU08 · Publicar versión legal")
def publicar_version(id_version: int, request: Request, staff: MiembroStaff = Depends(ESCRITURA), db: Session = Depends(get_db)):
    v = obtener(db, VersionLegal, id_version, "La versión")
    if v.estado != "borrador":
        raise ApiError(409, "ALREADY_PUBLISHED", "Esta versión ya fue publicada.")
    if v.fecha_vigencia < hoy_local():
        raise ApiError(422, "PAST_EFFECTIVE_DATE", "La fecha de vigencia no puede estar en el pasado.")
    for anterior in db.scalars(select(VersionLegal).where(VersionLegal.tipo_documento == v.tipo_documento,
                                                         VersionLegal.estado == "publicada")):
        anterior.estado = "reemplazada"
    v.estado, v.fecha_publicacion = "publicada", utcnow()
    registrar(db, actor=staff, accion="legal.publicar", tipo_entidad="version_legal", id_entidad=v.id_version,
              despues={"documento": v.tipo_documento, "version": f"{v.version_mayor}.{v.version_menor}",
                       "requiere_reaceptacion": v.requiere_reaceptacion}, request=request)
    db.commit()
    return version_out(v)


@router.get("/legales/publico/{tipo}", response_model=VersionOut, summary="Versión vigente (pública, la consume la app)")
def vigente(tipo: Literal["terminos", "privacidad"], db: Session = Depends(get_db)):
    v = db.scalar(select(VersionLegal).where(VersionLegal.tipo_documento == tipo, VersionLegal.estado == "publicada"))
    if v is None:
        raise ApiError(404, "NOT_FOUND", "No hay una versión publicada.")
    return version_out(v)
