import pyotp

from .conftest import API, PWD, login


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
    t1 = login(client).json()["refresh_token"]
    r = client.post(f"{API}/auth/refresh", json={"refresh_token": t1})
    assert r.status_code == 200
    t2 = r.json()["refresh_token"]
    # reusar el token ya rotado revoca todas las sesiones…
    assert client.post(f"{API}/auth/refresh", json={"refresh_token": t1}).status_code == 401
    # …incluida la nueva
    assert client.post(f"{API}/auth/refresh", json={"refresh_token": t2}).status_code == 401


def test_logout_revoca_refresh(client):
    body = login(client).json()
    h = {"Authorization": f"Bearer {body['access_token']}"}
    assert client.post(f"{API}/auth/logout", json={"refresh_token": body["refresh_token"]}, headers=h).status_code == 204
    assert client.post(f"{API}/auth/refresh", json={"refresh_token": body["refresh_token"]}).status_code == 401


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
