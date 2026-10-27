"""Contenidos y productos: CU17 Gestionar contenido · CU18 Publicar contenido · CU19 Gestionar catálogo de productos
· CU20 Revisar perfiles de cuidadoras."""
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, Field, HttpUrl, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..audit import diff, registrar
from ..db import get_db, utcnow
from ..deps import requiere
from ..errors import ApiError
from ..models import Contenido, MiembroStaff, PerfilCuidadora, Producto, UsuarioApp
from ..schemas import Page
from ..util import obtener, paginar, snap

router = APIRouter(tags=["Contenidos y productos"])
C_LECT, C_ESC = requiere("contenido", "lectura"), requiere("contenido", "escritura")
M_LECT, M_ESC = requiere("marketplace", "lectura"), requiere("marketplace", "escritura")


# ================================================================ CU17 / CU18 contenido
class ContenidoIn(BaseModel):
    tipo: Literal["chiste", "noticia"]
    titulo: str = Field(min_length=3, max_length=160)
    cuerpo: str = Field(min_length=10, max_length=4000)
    etiquetas: list[str] = Field(default_factory=list, max_length=10)


class ContenidoUpdateIn(BaseModel):
    titulo: str | None = Field(None, min_length=3, max_length=160)
    cuerpo: str | None = Field(None, min_length=10, max_length=4000)
    etiquetas: list[str] | None = Field(None, max_length=10)


class PublicarIn(BaseModel):
    fecha_programada: datetime | None = None  # vacío = publicar ahora


class ContenidoOut(BaseModel):
    id_contenido: int
    tipo: str
    titulo: str
    cuerpo: str
    etiquetas: list[str]
    estado: str
    fecha_programada: datetime | None
    fecha_publicacion: datetime | None
    fecha_creacion: datetime


def _tags(v: list[str] | None) -> str | None:
    return ",".join(sorted({t.strip().lower() for t in v if t.strip()})) if v else None


def contenido_out(c: Contenido) -> ContenidoOut:
    return ContenidoOut(id_contenido=c.id_contenido, tipo=c.tipo, titulo=c.titulo, cuerpo=c.cuerpo,
                        etiquetas=c.etiquetas.split(",") if c.etiquetas else [], estado=c.estado,
                        fecha_programada=c.fecha_programada, fecha_publicacion=c.fecha_publicacion,
                        fecha_creacion=c.fecha_creacion)


def publicar_programados(db: Session) -> int:
    """Pasa a «publicado» lo programado cuya fecha ya llegó (lo invoca el listado y el job)."""
    now = utcnow()
    pend = db.scalars(select(Contenido).where(Contenido.estado == "programado", Contenido.fecha_programada <= now,
                                              Contenido.fecha_eliminacion.is_(None))).all()
    for c in pend:
        c.estado, c.fecha_publicacion = "publicado", c.fecha_programada
    if pend:
        db.commit()
    return len(pend)


@router.get("/contenidos", response_model=Page[ContenidoOut], summary="Listar contenido curado")
def listar_contenido(tipo: str | None = None, estado: str | None = None, q: str | None = Query(None, max_length=120),
                     page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                     _: MiembroStaff = Depends(C_LECT), db: Session = Depends(get_db)):
    publicar_programados(db)
    stmt = select(Contenido).where(Contenido.fecha_eliminacion.is_(None))
    if tipo:
        stmt = stmt.where(Contenido.tipo == tipo)
    if estado:
        stmt = stmt.where(Contenido.estado == estado)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(func.lower(Contenido.titulo).like(like), func.lower(Contenido.etiquetas).like(like)))
    return paginar(db, stmt.order_by(Contenido.fecha_creacion.desc()), page, page_size, contenido_out)


@router.post("/contenidos", response_model=ContenidoOut, status_code=201, summary="CU17 · Crear contenido (borrador)")
def crear_contenido(data: ContenidoIn, request: Request, staff: MiembroStaff = Depends(C_ESC), db: Session = Depends(get_db)):
    c = Contenido(tipo=data.tipo, titulo=data.titulo.strip(), cuerpo=data.cuerpo.strip(), etiquetas=_tags(data.etiquetas))
    db.add(c)
    db.flush()
    registrar(db, actor=staff, accion="contenido.crear", tipo_entidad="contenido", id_entidad=c.id_contenido,
              despues={"tipo": c.tipo, "titulo": c.titulo}, request=request)
    db.commit()
    return contenido_out(c)


@router.patch("/contenidos/{id_contenido}", response_model=ContenidoOut, summary="CU17 · Editar contenido")
def editar_contenido(id_contenido: int, data: ContenidoUpdateIn, request: Request, staff: MiembroStaff = Depends(C_ESC),
                     db: Session = Depends(get_db)):
    c = obtener(db, Contenido, id_contenido, "El contenido")
    if c.fecha_eliminacion:
        raise ApiError(404, "NOT_FOUND", "El contenido no existe.")
    antes = snap(c, ["titulo", "cuerpo", "etiquetas"])
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(c, k, _tags(v) if k == "etiquetas" else v.strip())
    a, d = diff(antes, snap(c, ["titulo", "cuerpo", "etiquetas"]))
    if d:
        registrar(db, actor=staff, accion="contenido.editar", tipo_entidad="contenido", id_entidad=c.id_contenido,
                  antes=a, despues=d, request=request)
    db.commit()
    return contenido_out(c)


@router.post("/contenidos/{id_contenido}/publicar", response_model=ContenidoOut,
             summary="CU18 · Publicar ahora o programar la publicación")
def publicar_contenido(id_contenido: int, data: PublicarIn, request: Request, staff: MiembroStaff = Depends(C_ESC),
                       db: Session = Depends(get_db)):
    c = obtener(db, Contenido, id_contenido, "El contenido")
    if c.estado == "publicado":
        raise ApiError(409, "ALREADY_PUBLISHED", "El contenido ya está publicado.")
    now = utcnow()
    if data.fecha_programada and data.fecha_programada > now:
        c.estado, c.fecha_programada = "programado", data.fecha_programada
    else:
        c.estado, c.fecha_publicacion, c.fecha_programada = "publicado", now, None
    registrar(db, actor=staff, accion="contenido.publicar", tipo_entidad="contenido", id_entidad=c.id_contenido,
              despues={"estado": c.estado, "fecha_programada": c.fecha_programada}, request=request)
    db.commit()
    return contenido_out(c)


@router.post("/contenidos/{id_contenido}/archivar", response_model=ContenidoOut, summary="Retirar contenido del feed")
def archivar_contenido(id_contenido: int, request: Request, staff: MiembroStaff = Depends(C_ESC),
                       db: Session = Depends(get_db)):
    c = obtener(db, Contenido, id_contenido, "El contenido")
    antes = c.estado
    c.estado = "archivado"
    registrar(db, actor=staff, accion="contenido.archivar", tipo_entidad="contenido", id_entidad=c.id_contenido,
              antes={"estado": antes}, despues={"estado": "archivado"}, request=request)
    db.commit()
    return contenido_out(c)


@router.delete("/contenidos/{id_contenido}", status_code=204, summary="Eliminar contenido (borrado lógico)")
def eliminar_contenido(id_contenido: int, request: Request, staff: MiembroStaff = Depends(C_ESC),
                       db: Session = Depends(get_db)):
    c = obtener(db, Contenido, id_contenido, "El contenido")
    if c.estado == "publicado":
        raise ApiError(409, "PUBLISHED", "Archiva el contenido antes de eliminarlo.")
    c.fecha_eliminacion = utcnow()
    registrar(db, actor=staff, accion="contenido.eliminar", tipo_entidad="contenido", id_entidad=c.id_contenido,
              request=request)
    db.commit()
    return Response(status_code=204)


# ================================================================ CU19 productos
class ProductoIn(BaseModel):
    nombre: str = Field(min_length=3, max_length=160)
    categoria: str = Field(min_length=3, max_length=60)
    proveedor: str = Field(min_length=2, max_length=120)
    precio_referencial: int | None = Field(None, ge=0)
    url_externa: HttpUrl
    url_imagen: HttpUrl | None = None

    @field_validator("url_externa")
    @classmethod
    def _https(cls, v):
        if v.scheme != "https":
            raise ValueError("El enlace debe usar https.")
        return v


class ProductoUpdateIn(BaseModel):
    nombre: str | None = Field(None, min_length=3, max_length=160)
    categoria: str | None = Field(None, min_length=3, max_length=60)
    proveedor: str | None = Field(None, min_length=2, max_length=120)
    precio_referencial: int | None = Field(None, ge=0)
    url_externa: HttpUrl | None = None
    url_imagen: HttpUrl | None = None
    estado: Literal["borrador", "publicado", "archivado"] | None = None


class ProductoOut(BaseModel):
    id_producto: int
    nombre: str
    categoria: str
    proveedor: str
    precio_referencial: int | None
    url_externa: str
    url_imagen: str | None
    estado: str
    fecha_creacion: datetime


def producto_out(p: Producto) -> ProductoOut:
    return ProductoOut(**snap(p, list(ProductoOut.model_fields)))


CAMPOS_PRODUCTO = ["nombre", "categoria", "proveedor", "precio_referencial", "url_externa", "url_imagen", "estado"]


@router.get("/productos", response_model=Page[ProductoOut], summary="Catálogo de productos de apoyo")
def listar_productos(estado: str | None = None, categoria: str | None = None, q: str | None = Query(None, max_length=120),
                     page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                     _: MiembroStaff = Depends(M_LECT), db: Session = Depends(get_db)):
    stmt = select(Producto)
    if estado:
        stmt = stmt.where(Producto.estado == estado)
    if categoria:
        stmt = stmt.where(Producto.categoria == categoria)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(func.lower(Producto.nombre).like(like), func.lower(Producto.proveedor).like(like)))
    return paginar(db, stmt.order_by(Producto.nombre), page, page_size, producto_out)


@router.post("/productos", response_model=ProductoOut, status_code=201, summary="CU19 · Agregar producto")
def crear_producto(data: ProductoIn, request: Request, staff: MiembroStaff = Depends(M_ESC), db: Session = Depends(get_db)):
    vals = data.model_dump()
    vals["url_externa"] = str(data.url_externa)
    vals["url_imagen"] = str(data.url_imagen) if data.url_imagen else None
    p = Producto(**vals, estado="borrador")
    db.add(p)
    db.flush()
    registrar(db, actor=staff, accion="producto.crear", tipo_entidad="producto", id_entidad=p.id_producto,
              despues={"nombre": p.nombre}, request=request)
    db.commit()
    return producto_out(p)


@router.patch("/productos/{id_producto}", response_model=ProductoOut, summary="CU19 · Editar, publicar o archivar producto")
def editar_producto(id_producto: int, data: ProductoUpdateIn, request: Request, staff: MiembroStaff = Depends(M_ESC),
                    db: Session = Depends(get_db)):
    p = obtener(db, Producto, id_producto, "El producto")
    antes = snap(p, CAMPOS_PRODUCTO)
    for k, v in data.model_dump(exclude_unset=True).items():
        if k in ("url_externa", "url_imagen") and v is not None:
            v = str(v)
            if k == "url_externa" and not v.startswith("https://"):
                raise ApiError(422, "VALIDATION_ERROR", "El enlace debe usar https.")
        setattr(p, k, v)
    a, d = diff(antes, snap(p, CAMPOS_PRODUCTO))
    if d:
        registrar(db, actor=staff, accion="producto.editar", tipo_entidad="producto", id_entidad=p.id_producto,
                  antes=a, despues=d, request=request)
    db.commit()
    return producto_out(p)


# ================================================================ CU20 cuidadoras
class CuidadoraOut(BaseModel):
    id_perfil: int
    id_usuario: int
    nombre: str
    email: str
    zona: str
    especialidades: list[str]
    idiomas: list[str]
    certificaciones_verificadas: int
    calificacion_promedio: float | None
    estado_publicacion: str
    motivo_estado: str | None
    revisor: str | None
    fecha_envio: datetime
    fecha_revision: datetime | None


class RevisionIn(BaseModel):
    decision: Literal["aprobado", "suspendido"]
    motivo: str | None = Field(None, max_length=1000)


def cuidadora_out(p: PerfilCuidadora) -> CuidadoraOut:
    return CuidadoraOut(id_perfil=p.id_perfil, id_usuario=p.id_usuario, nombre=p.usuario.nombre, email=p.usuario.email,
                        zona=p.zona, especialidades=(p.especialidades or "").split(",") if p.especialidades else [],
                        idiomas=(p.idiomas or "").split(",") if p.idiomas else [],
                        certificaciones_verificadas=p.certificaciones_verificadas,
                        calificacion_promedio=float(p.calificacion_promedio) if p.calificacion_promedio is not None else None,
                        estado_publicacion=p.estado_publicacion, motivo_estado=p.motivo_estado,
                        revisor=p.revisor.nombre_completo if p.revisor else None, fecha_envio=p.fecha_envio,
                        fecha_revision=p.fecha_revision)


@router.get("/cuidadoras", response_model=Page[CuidadoraOut], summary="Perfiles de cuidadoras en la vitrina")
def listar_cuidadoras(estado: str | None = None, q: str | None = Query(None, max_length=120), page: int = Query(1, ge=1),
                      page_size: int = Query(20, ge=1, le=100), _: MiembroStaff = Depends(M_LECT),
                      db: Session = Depends(get_db)):
    stmt = select(PerfilCuidadora).join(UsuarioApp, PerfilCuidadora.id_usuario == UsuarioApp.id_usuario)
    if estado:
        stmt = stmt.where(PerfilCuidadora.estado_publicacion == estado)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(func.lower(UsuarioApp.nombre).like(like), func.lower(PerfilCuidadora.zona).like(like)))
    return paginar(db, stmt.order_by(PerfilCuidadora.fecha_envio.desc()), page, page_size, cuidadora_out)


@router.post("/cuidadoras/{id_perfil}/revision", response_model=CuidadoraOut, summary="CU20 · Aprobar o suspender perfil")
def revisar_cuidadora(id_perfil: int, data: RevisionIn, request: Request, staff: MiembroStaff = Depends(M_ESC),
                      db: Session = Depends(get_db)):
    p = obtener(db, PerfilCuidadora, id_perfil, "El perfil")
    if data.decision == "aprobado" and p.certificaciones_verificadas < 1:
        raise ApiError(409, "CERTIFICATION_REQUIRED", "Para aprobar, la cuidadora debe tener al menos una certificación verificada.")
    if data.decision == "suspendido" and not (data.motivo and len(data.motivo.strip()) >= 10):
        raise ApiError(422, "REASON_REQUIRED", "Para suspender indica el motivo (mínimo 10 caracteres); se notificará a la cuidadora.")
    antes = p.estado_publicacion
    p.estado_publicacion, p.motivo_estado = data.decision, (data.motivo or None)
    p.id_staff_revisor, p.fecha_revision = staff.id_staff, utcnow()
    registrar(db, actor=staff, accion="cuidadora.revisar", tipo_entidad="perfil_cuidadora", id_entidad=p.id_perfil,
              antes={"estado": antes}, despues={"estado": data.decision, "motivo": data.motivo}, request=request)
    db.commit()
    db.refresh(p)
    return cuidadora_out(p)
