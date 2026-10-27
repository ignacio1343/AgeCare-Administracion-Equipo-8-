"""Dependencias de seguridad: staff autenticado y control de acceso por rol (RBAC)."""
import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .errors import ApiError
from .models import MiembroStaff, PermisoRol
from .security import decode_access_token

bearer = HTTPBearer(auto_error=False)


def current_staff(cred: HTTPAuthorizationCredentials | None = Depends(bearer),
                  db: Session = Depends(get_db)) -> MiembroStaff:
    if cred is None:
        raise ApiError(401, "UNAUTHORIZED", "Tu sesión de administración expiró. Vuelve a iniciar sesión.")
    try:
        data = decode_access_token(cred.credentials)
    except jwt.PyJWTError:
        raise ApiError(401, "UNAUTHORIZED", "Tu sesión de administración expiró. Vuelve a iniciar sesión.")
    staff = db.get(MiembroStaff, int(data["sub"]))
    if staff is None or staff.estado != "activo":
        raise ApiError(401, "UNAUTHORIZED", "Tu sesión de administración expiró. Vuelve a iniciar sesión.")
    return staff


def permisos_de(db: Session, codigo_rol: str) -> dict[str, str]:
    rows = db.scalars(select(PermisoRol).where(PermisoRol.codigo_rol == codigo_rol)).all()
    return {p.modulo: p.nivel_acceso for p in rows}


def requiere(modulo: str, nivel: str = "lectura"):
    """Uso: Depends(requiere("soporte", "escritura")). Escritura implica lectura."""

    def _check(staff: MiembroStaff = Depends(current_staff), db: Session = Depends(get_db)) -> MiembroStaff:
        acceso = permisos_de(db, staff.codigo_rol).get(modulo)
        if acceso is None or (nivel == "escritura" and acceso != "escritura"):
            raise ApiError(403, "FORBIDDEN", "Tu rol no tiene permisos sobre este módulo.")
        return staff

    return _check
