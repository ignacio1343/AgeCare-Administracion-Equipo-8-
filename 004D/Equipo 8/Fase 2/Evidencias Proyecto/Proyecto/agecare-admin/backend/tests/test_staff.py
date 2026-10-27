from urllib.parse import parse_qs, urlparse

from .conftest import API, RH, con_cookie, login


def _token(enlace):
    return parse_qs(urlparse(enlace).query)["token"][0]


def test_crear_invitar_activar_e_ingresar(client, auth):
    h = auth("admin")
    r = client.post(f"{API}/staff", headers=h, json={"nombre_completo": "Nueva Agente", "email": "nueva@wellq.co.uk",
                                                    "codigo_rol": "soporte"})
    assert r.status_code == 201, r.text
    assert r.json()["staff"]["estado"] == "pendiente"
    token = _token(r.json()["enlace_activacion"])
    # antes de activar no puede entrar
    assert login(client, "nueva@wellq.co.uk", password="x").status_code == 401
    assert client.get(f"{API}/auth/activacion/{token}").json()["email"] == "nueva@wellq.co.uk"
    assert client.post(f"{API}/auth/activacion", json={"token": token, "password": "corta"}).status_code == 422
    assert client.post(f"{API}/auth/activacion", json={"token": token, "password": "Segura2026"}).status_code == 204
    assert login(client, "nueva@wellq.co.uk", password="Segura2026").status_code == 200
    # el enlace es de un solo uso
    assert client.post(f"{API}/auth/activacion", json={"token": token, "password": "Segura2026"}).status_code == 410


def test_reglas_de_creacion(client, auth):
    h = auth("admin")
    base = {"nombre_completo": "X Y", "codigo_rol": "analista"}
    assert client.post(f"{API}/staff", headers=h, json=base | {"email": "x@gmail.com"}).json()["error"]["code"] == "DOMAIN_NOT_ALLOWED"
    assert client.post(f"{API}/staff", headers=h, json=base | {"email": "soporte@wellq.co.uk"}).json()["error"]["code"] == "EMAIL_IN_USE"


def test_solo_admin_gestiona_staff(client, auth):
    for rol in ("soporte", "analista", "editor"):
        assert client.get(f"{API}/staff", headers=auth(rol)).status_code == 403


def test_no_puede_desactivarse_ni_quitar_ultimo_admin(client, auth):
    h = auth("admin")
    me = client.get(f"{API}/auth/me", headers=h).json()
    r = client.patch(f"{API}/staff/{me['id_staff']}", headers=h, json={"estado": "inactivo"})
    assert r.json()["error"]["code"] == "CANNOT_DISABLE_SELF"
    r = client.patch(f"{API}/staff/{me['id_staff']}", headers=h, json={"codigo_rol": "analista"})
    assert r.json()["error"]["code"] == "LAST_ADMIN"


def test_desactivar_revoca_sesiones_y_queda_en_auditoria(client, auth):
    r_sop = login(client, "soporte")
    sesion, token_sop = r_sop.json(), r_sop.cookies["aca_refresh"]
    h = auth("admin")
    lista = client.get(f"{API}/staff", headers=h, params={"q": "soporte"}).json()["items"]
    r = client.patch(f"{API}/staff/{lista[0]['id_staff']}", headers=h, json={"estado": "inactivo"})
    assert r.status_code == 200 and r.json()["estado"] == "inactivo"
    con_cookie(client, token_sop)
    assert client.post(f"{API}/auth/refresh", headers=RH).status_code == 401
    assert client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {sesion['access_token']}"}).status_code == 401
    log = client.get(f"{API}/auditoria", headers=h, params={"accion": "staff."}).json()
    assert log["items"][0]["accion"] == "staff.actualizar"
    assert '"inactivo"' in log["items"][0]["valor_nuevo"]
