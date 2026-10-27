"""Pruebas unitarias: funciones puras de seguridad, pasarela, monitor y reglas de estado (sin HTTP)."""

import jwt
import pyotp
import pytest

from app import monitor, pasarela, security
from app.models import TRANSICIONES_INCIDENTE, TRANSICIONES_TICKET


def test_hash_argon2id_y_verificacion():
    h = security.hash_password("Clave1234")
    assert h.startswith("$argon2id$") and "Clave1234" not in h
    assert security.verify_password("Clave1234", h)
    assert not security.verify_password("otra", h)


def test_argon2_parametros_owasp_y_rehash():
    h = security.hash_password("Clave1234")
    assert "$m=19456,t=2,p=1$" in h and not security.needs_rehash(h)
    from argon2 import PasswordHasher
    antiguo = PasswordHasher().hash("Clave1234")  # perfil anterior (64 MiB, t=3, p=4)
    assert security.verify_password("Clave1234", antiguo) and security.needs_rehash(antiguo)


def test_verificacion_tolera_hash_vacio_o_invalido():
    assert not security.verify_password("x", None)
    assert not security.verify_password("x", "no-es-un-hash")


def test_jwt_de_acceso_contiene_rol_y_expira():
    tok = security.create_access_token(7, "soporte")
    data = security.decode_access_token(tok)
    assert data["sub"] == "7" and data["rol"] == "soporte" and data["typ"] == "access"
    assert 0 < data["exp"] - data["iat"] <= 15 * 60


def test_jwt_manipulado_es_rechazado():
    tok = security.create_access_token(1, "admin")
    cab, cuerpo, firma = tok.split(".")
    with pytest.raises(jwt.InvalidTokenError):
        security.decode_access_token(f"{cab}.{cuerpo}.{firma[::-1]}")


def test_totp_valido_e_invalido():
    secreto = security.new_totp_secret()
    assert security.verify_totp(secreto, pyotp.TOTP(secreto).now())
    assert not security.verify_totp(secreto, "000000") or pyotp.TOTP(secreto).now() == "000000"
    assert not security.verify_totp(None, "123456")


def test_tokens_opacos_unicos_y_hash_sha256():
    a, b = security.new_opaque_token(), security.new_opaque_token()
    assert a != b and len(a) >= 60
    assert len(security.sha256(a)) == 64 and security.sha256(a) == security.sha256(a)


def test_firma_hmac_del_webhook():
    cuerpo = b'{"id_evento":"ev_1","tipo":"pago_aprobado"}'
    firma = pasarela.firmar(cuerpo)
    assert pasarela.firma_valida(cuerpo, firma)
    assert not pasarela.firma_valida(cuerpo + b" ", firma)
    assert not pasarela.firma_valida(cuerpo, None)


def test_percentiles_del_monitor():
    vals = list(range(1, 101))
    assert monitor._percentil(vals, 0.5) == 50 or monitor._percentil(vals, 0.5) == 51
    assert monitor._percentil(vals, 0.95) in (95, 96)
    assert monitor._percentil([], 0.95) is None


def test_transiciones_de_ticket():
    assert TRANSICIONES_TICKET["abierto"] == {"en_curso"}
    assert "resuelto" in TRANSICIONES_TICKET["en_curso"]
    assert TRANSICIONES_TICKET["cerrado"] == set()
    assert "cerrado" not in TRANSICIONES_TICKET["abierto"]


def test_transiciones_de_incidente_terminales():
    assert TRANSICIONES_INCIDENTE["resuelto"] == set()
    assert {"en_observacion", "resuelto"} <= TRANSICIONES_INCIDENTE["investigando"]


def test_planificador_registra_fallos_en_una_linea(caplog):
    import logging

    from sqlalchemy.exc import OperationalError

    from app.planificador import _Fallos
    f = _Fallos()
    exc = OperationalError("SELECT 1", {}, Exception("connection refused\nIs the server running on host?"))
    with caplog.at_level(logging.INFO, logger="planificador"):
        for _ in range(12):
            f.fallo(exc)
        f.ok()
    errores = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errores) == 2  # ciclo 1 y ciclo 10, no 12 trazas
    assert all("\n" not in r.getMessage() and r.exc_info is None for r in errores)
    assert "OperationalError: connection refused" in errores[0].getMessage()
    assert "recuperado tras 12" in caplog.records[-1].getMessage()
