"""Contraseñas (Argon2id), JWT de acceso, refresh tokens y TOTP."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from .config import get_settings

# Argon2id con la configuración mínima recomendada por OWASP (Password Storage Cheat Sheet):
# 19 MiB de memoria, 2 iteraciones, 1 hilo. El perfil por defecto de argon2-cffi (64 MiB, t=3, p=4) tardaba ~110 ms
# por verificación y saturaba los 2 núcleos con 50 ingresos simultáneos (DEF-09: login p95 2,7 s); este tarda ~20 ms
# y sigue dentro del estándar. Los hashes antiguos se migran solos al iniciar sesión (ver needs_rehash).
_ph = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)


def hash_password(password: str) -> str:
    return _ph.hash(password)


def needs_rehash(hashed: str) -> bool:
    try:
        return _ph.check_needs_rehash(hashed)
    except InvalidHashError:
        return False


def verify_password(password: str, hashed: str | None) -> bool:
    if not hashed:
        return False
    try:
        return _ph.verify(hashed, password)
    except (VerificationError, InvalidHashError):
        return False


# Hash de referencia para igualar el tiempo de respuesta cuando el correo no existe
DUMMY_HASH = _ph.hash("contraseña-inexistente")


def create_access_token(id_staff: int, rol: str) -> str:
    s = get_settings()
    now = datetime.now(timezone.utc)
    payload = {"sub": str(id_staff), "rol": rol, "iat": now, "exp": now + timedelta(minutes=s.access_token_minutes),
               "typ": "access"}
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    s = get_settings()
    data = jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])
    if data.get("typ") != "access":
        raise jwt.InvalidTokenError("tipo de token inválido")
    return data


def new_opaque_token() -> str:
    """Token aleatorio (refresh o activación). Solo se guarda su hash SHA-256."""
    return secrets.token_urlsafe(48)


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def new_totp_secret() -> str:
    return pyotp.random_base32()


def totp_uri(secret: str, email: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=get_settings().totp_issuer)


def verify_totp(secret: str | None, code: str | None) -> bool:
    if not secret or not code:
        return False
    return pyotp.TOTP(secret).verify(code.strip(), valid_window=1)
