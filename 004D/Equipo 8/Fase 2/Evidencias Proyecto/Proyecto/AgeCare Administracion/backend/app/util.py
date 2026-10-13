"""Utilidades compartidas por los routers."""
from typing import Any, Callable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .errors import ApiError
from .schemas import Page


def paginar(db: Session, stmt, page: int, page_size: int, mapper: Callable[[Any], Any] = lambda x: x) -> Page:
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    rows = db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).unique().all()
    return Page(items=[mapper(r) for r in rows], page=page, page_size=page_size, total=total or 0)


def obtener(db: Session, modelo, ident, nombre: str = "El recurso"):
    obj = db.get(modelo, ident)
    if obj is None:
        raise ApiError(404, "NOT_FOUND", f"{nombre} no existe.")
    return obj


def snap(obj, campos: list[str]) -> dict:
    return {c: getattr(obj, c) for c in campos}
