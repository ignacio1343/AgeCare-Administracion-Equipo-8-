import pyotp

from .conftest import RH, con_cookie, API, PWD, login


def test_login_ok_y_perfil_con_permisos(client):
    r = login(client, "soporte")
    assert r.status_code == 200
    body = r.json()
    assert body["staff"]["codigo_rol"] == "soporte"
    assert body["staff"]["permisos"]["soporte"] == "escritura"
    assert "staff" not in body["staff"]["permisos"]  # soporte no gestiona staff
    me = client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200 and me.json()["email"] == "soporte@wellq.co.uk"


def test_login_no_revela_si_el_correo_existe(client):
    a = login(client, "admin", password="incorrecta1")
    b = login(client, "noexiste@wellq.co.uk", password="incorrecta1")
    assert a.status_code == b.status_code == 401
    assert a.json()["error"]["code"] == b.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_bloqueo_tras_5_intentos(client):
    for _ in range(5):
        assert login(client, "admin", password="mala12345").status_code == 401
    r = login(client, "admin")  # incluso con la clave correcta
    assert r.status_code == 423 and r.json()["error"]["code"] == "ACCOUNT_LOCKED"


def test_sin_token_401_y_formato_de_error(client):
    r = client.get(f"{API}/auth/me")
    assert r.status_code == 401
    err = r.json()["error"]
    assert err["code"] == "UNAUTHORIZED" and err["request_id"]


def test_refresh_rota_y_detecta_reuso(client):
    r = login(client)
    assert "refresh_token" not in r.json()  # el refresh token ya no llega al JavaScript
    t1 = r.cookies["aca_refresh"]
    r = client.post(f"{API}/auth/refresh", headers=RH)
    assert r.status_code == 200 and r.json()["access_token"]
    t2 = r.cookies["aca_refresh"]
    assert t2 != t1
    # reusar el token ya rotado revoca todas las sesiones…
    con_cookie(client, t1)
    assert client.post(f"{API}/auth/refresh", headers=RH).status_code == 401
    # …incluida la nueva
    con_cookie(client, t2)
    assert client.post(f"{API}/auth/refresh", headers=RH).status_code == 401


def test_cookie_refresh_httponly_y_restringida(client):
    sc = login(client).headers["set-cookie"].lower()
    assert "aca_refresh=" in sc and "httponly" in sc and "samesite=strict" in sc and "path=/api/v1/auth" in sc


def test_refresh_exige_cabecera_anti_csrf(client):
    login(client)
    r = client.post(f"{API}/auth/refresh")
    assert r.status_code == 403 and r.json()["error"]["code"] == "CSRF_HEADER_REQUIRED"
    con_cookie(client, None)
    assert client.post(f"{API}/auth/refresh", headers=RH).status_code == 401  # sin cookie


def test_logout_revoca_refresh(client):
    r = login(client)
    body, token = r.json(), r.cookies["aca_refresh"]
    h = {"Authorization": f"Bearer {body['access_token']}", **RH}
    r = client.post(f"{API}/auth/logout", headers=h)
    assert r.status_code == 204 and 'aca_refresh=""' in r.headers["set-cookie"]
    con_cookie(client, token)
    assert client.post(f"{API}/auth/refresh", headers=RH).status_code == 401


def test_flujo_segundo_factor(client, auth):
    h = auth("admin")
    setup = client.post(f"{API}/auth/mfa/configurar", headers=h)
    assert setup.status_code == 200 and setup.json()["qr_svg"].startswith("<svg")
    secreto = setup.json()["secreto"]
    assert client.post(f"{API}/auth/mfa/confirmar", json={"codigo_otp": "000000"}, headers=h).status_code == 422
    ok = client.post(f"{API}/auth/mfa/confirmar", json={"codigo_otp": pyotp.TOTP(secreto).now()}, headers=h)
    assert ok.status_code == 200 and ok.json()["mfa_habilitado"] is True
    # ahora el login exige el código
    assert login(client).json()["error"]["code"] == "OTP_REQUIRED"
    assert login(client, codigo_otp="123456").json()["error"]["code"] == "OTP_INVALID"
    assert login(client, codigo_otp=pyotp.TOTP(secreto).now()).status_code == 200


def test_login_migra_hash_argon2_antiguo(client):
    from argon2 import PasswordHasher

    from app.db import SessionLocal
    from app.models import MiembroStaff
    with SessionLocal() as db:
        s = db.query(MiembroStaff).filter_by(email="soporte@wellq.co.uk").one()
        s.password_hash = PasswordHasher().hash(PWD)
        db.commit()
    assert login(client, "soporte").status_code == 200
    with SessionLocal() as db:
        assert "$m=19456,t=2,p=1$" in db.query(MiembroStaff).filter_by(email="soporte@wellq.co.uk").one().password_hash
