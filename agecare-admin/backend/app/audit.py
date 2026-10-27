"""Bitácora de auditoría: toda acción de escritura deja un registro (OE4)."""
import json
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from .models import MiembroStaff, RegistroAuditoria

SENSIBLES = {"password", "password_hash", "secreto_mfa", "token", "refresh_token", "token_activacion_hash"}


def _limpio(data: Any) -> str | None:
    if data is None:
        return None
    if isinstance(data, dict):
        data = {k: ("***" if k in SENSIBLES else v) for k, v in data.items()}
    return json.dumps(data, ensure_ascii=False, default=str)


def client_ip(request: Request | None) -> str | None:
    if request is None:
        return None
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()[:45]
    return request.client.host[:45] if request.client else None


def registrar(db: Session, *, actor: MiembroStaff | None, accion: str, tipo_entidad: str,
              id_entidad: Any = None, antes: Any = None, despues: Any = None,
              request: Request | None = None) -> RegistroAuditoria:
    reg = RegistroAuditoria(
        id_staff_actor=actor.id_staff if actor else None,
        accion=accion,
        tipo_entidad=tipo_entidad,
        id_entidad=str(id_entidad) if id_entidad is not None else None,
        valor_anterior=_limpio(antes),
        valor_nuevo=_limpio(despues),
        ip=client_ip(request),
    )
    db.add(reg)
    return reg


def diff(antes: dict, despues: dict) -> tuple[dict, dict]:
    """Devuelve solo los campos que cambiaron."""
    keys = [k for k in despues if antes.get(k) != despues.get(k)]
    return {k: antes.get(k) for k in keys}, {k: despues.get(k) for k in keys}
