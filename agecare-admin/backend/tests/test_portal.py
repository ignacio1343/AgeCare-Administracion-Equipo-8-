"""Portal web (v0.6.0): registro del representante con SMS, pagos (simulado y Webpay), residentes, estado en tiempo
real, ficha del cuidador con avisos, contenidos, tickets de ayuda y de contraseña, y cuentas creadas desde la consola."""
from datetime import date, timedelta

import pytest

from app import rut, sms, webpay
from app.config import get_settings
from app.db import SessionLocal, utcnow
from app.models import (Contenido, MensajeWhatsapp, NotificacionApp, OrdenPago, Suscripcion, Ticket, TransaccionPago,
                        UsuarioApp, VerificacionSms)
from tests.conftest import API, RH

P = f"{API}/portal"
CLAVE = "Portal1234"
RUT_REP, RUT_RES, RUT_RES2, RUT_CUI = "11.111.111-1", "12.345.678-5", "9.876.543-3", "15.555.553-K"


def _rut_valido(cuerpo: int) -> str:
    return f"{cuerpo}-{rut.dv(str(cuerpo))}"


def _datos(**extra):
    d = {"email": "rep@example.com", "rut": RUT_REP, "nombres": "Carla", "primer_apellido": "Rojas",
         "segundo_apellido": "Vidal", "password": CLAVE, "password2": CLAVE, "pais": "CL", "telefono": "9 7565 8296",
         "acepta_terminos": True, "acepta_whatsapp": True}
    d.update(extra)
    return d


def _registrar(client, **extra):
    r = client.post(f"{P}/registro", json=_datos(**extra))
    assert r.status_code == 201, r.text
    v = r.json()
    r = client.post(f"{P}/registro/confirmar", json={"verificacion": v["verificacion"], "codigo": v["codigo_demo"]})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _contratar(client, h, plan="platino", aprobar=True):
    r = client.post(f"{P}/representante/pagos", headers=h, json={"tipo": "alta", "codigo_plan": plan})
    assert r.status_code == 201, r.text
    o = r.json()
    if o["resultado"] == "listo":
        return o["id_suscripcion"]
    r = client.post(f"{P}/pagos/{o['orden_compra']}/simulado", headers=h, json={"aprobar": aprobar})
    assert r.status_code == 200, r.text
    return r.json()["id_suscripcion"]


def _residente(**extra):
    d = {"rut": RUT_RES, "primer_nombre": "Hilda", "primer_apellido": "Pérez", "segundo_apellido": "Soto",
         "email": "hilda@example.com", "fecha_nacimiento": "1941-05-02", "password": "Hilda2026", "password2": "Hilda2026"}
    d.update(extra)
    return d


def _login(client, usuario, password):
    r = client.post(f"{P}/auth/login", json={"usuario": usuario, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}, r.json()["usuario"]


def _familia(client, plan="platino"):
    """Representante registrado, plan pagado y residente creado. Devuelve (headers, id_suscripcion, id_paciente)."""
    h = _registrar(client)
    sid = _contratar(client, h, plan)
    r = client.post(f"{P}/representante/suscripciones/{sid}/residente", headers=h, json=_residente())
    assert r.status_code == 201, r.text
    return h, sid, r.json()["residente"]["id_paciente"]


def _cuidador(client, auth, id_paciente):
    r = client.post(f"{API}/usuarios", headers=auth("soporte"), json={
        "perfil": "cuidador", "rut": RUT_CUI, "nombres": "Juan", "primer_apellido": "Muñoz", "email": "juan@example.com",
        "id_pacientes": [id_paciente]})
    assert r.status_code == 201, r.text
    clave = r.json()["password_temporal"]
    h, me = _login(client, "juan@example.com", clave)
    assert me["debe_cambiar_password"]
    r = client.post(f"{P}/auth/cambiar-password", headers=h,
                    json={"actual": clave, "password": "Cuida2026", "password2": "Cuida2026"})
    assert r.status_code == 200 and not r.json()["debe_cambiar_password"]
    return h


# ---------------------------------------------------------------- RUT
def test_rut_modulo_11():
    assert rut.normalizar("11.111.111-1") == "11111111-1"
    assert rut.normalizar("15555553k") == "15555553-K"
    assert rut.normalizar("12.345.678-9") is None  # dígito verificador incorrecto
    assert rut.normalizar("abc") is None and rut.normalizar(None) is None
    assert rut.formatear("12345678-5") == "12.345.678-5"


# ---------------------------------------------------------------- registro con SMS (CU44)
def test_registro_validaciones(client):
    assert client.get(f"{P}/paises").json()[0] == {"codigo": "CL", "prefijo": "+56", "nombre": "Chile", "ejemplo": "9 1234 5678"}
    casos = [({"password2": "Otra12345"}, "coinciden"), ({"rut": "12.345.678-9"}, "RUT inválido"),
             ({"acepta_terminos": False}, "términos"), ({"password": "corta", "password2": "corta"}, "8 caracteres"),
             ({"nombres": "C4rla"}, "letras")]
    for extra, texto in casos:
        r = client.post(f"{P}/registro", json=_datos(**extra))
        assert r.status_code == 422 and texto in str(r.json()["error"]["details"]), (extra, r.text)
    r = client.post(f"{P}/registro", json=_datos(telefono="12345"))
    assert r.status_code == 422 and r.json()["error"]["details"][0]["field"] == "telefono"
    r = client.post(f"{P}/registro", json=_datos(pais="AR", telefono="9 11 2345 6789"))
    assert r.status_code == 201 and r.json()["telefono"].startswith("+549")
    r = client.post(f"{P}/registro", json=_datos(email="ana@example.com"))  # correo de un usuario existente
    assert r.status_code == 409 and r.json()["error"]["code"] == "EMAIL_EXISTS"


def test_registro_completo_y_rut_ya_registrado(client):
    h = _registrar(client)
    me = client.get(f"{P}/auth/me", headers=h).json()
    assert me["vistas"] == ["representante"] and me["rut"] == "11.111.111-1" and me["telefono"] == "+569 •••• 8296"
    assert me["whatsapp_habilitado"] and me["notificaciones_sin_leer"] == 1  # bienvenida
    with SessionLocal() as db:
        u = db.query(UsuarioApp).filter_by(email="rep@example.com").one()
        assert u.telefono == "+56975658296" and u.origen == "portal" and u.fecha_aceptacion_terminos
        v = db.query(VerificacionSms).one()
        assert v.estado == "verificada" and v.datos == "{}"  # el hash de la clave no queda en la verificación
    r = client.post(f"{P}/registro", json=_datos(email="otro@example.com"))
    assert r.status_code == 409 and r.json()["error"]["code"] == "RUT_EXISTS"


def test_codigo_sms_intentos_reenvio_y_expiracion(client):
    v = client.post(f"{P}/registro", json=_datos()).json()
    assert v["modo"] == "simulado" and len(v["codigo_demo"]) == 6 and v["intentos_restantes"] == 3
    malo = "000000" if v["codigo_demo"] != "000000" else "111111"
    r = client.post(f"{P}/registro/confirmar", json={"verificacion": v["verificacion"], "codigo": malo})
    assert r.status_code == 422 and r.json()["error"]["details"]["intentos_restantes"] == 2
    r = client.post(f"{P}/registro/reenviar", json={"verificacion": v["verificacion"]})
    assert r.status_code == 429 and r.json()["error"]["code"] == "RESEND_TOO_SOON"
    with SessionLocal() as db:  # pasan 61 segundos
        x = db.query(VerificacionSms).one()
        x.fecha_ultimo_envio = utcnow() - timedelta(seconds=61)
        db.commit()
    r = client.post(f"{P}/registro/reenviar", json={"verificacion": v["verificacion"]})
    assert r.status_code == 200 and r.json()["intentos_restantes"] == 3
    nuevo = r.json()["codigo_demo"]
    malo = "000000" if nuevo != "000000" else "111111"
    for i in range(2):
        assert client.post(f"{P}/registro/confirmar", json={"verificacion": v["verificacion"], "codigo": malo}).status_code == 422
    r = client.post(f"{P}/registro/confirmar", json={"verificacion": v["verificacion"], "codigo": malo})
    assert r.status_code == 429 and r.json()["error"]["code"] == "CODE_ATTEMPTS_EXCEEDED"
    r = client.post(f"{P}/registro/confirmar", json={"verificacion": v["verificacion"], "codigo": nuevo})
    assert r.status_code == 410  # bloqueada: hay que registrarse de nuevo
    v2 = client.post(f"{P}/registro", json=_datos()).json()
    with SessionLocal() as db:
        x = db.query(VerificacionSms).filter_by(estado="pendiente").one()
        x.fecha_expiracion = utcnow() - timedelta(seconds=1)
        db.commit()
    r = client.post(f"{P}/registro/confirmar", json={"verificacion": v2["verificacion"], "codigo": v2["codigo_demo"]})
    assert r.status_code == 410 and "venció" in r.json()["error"]["message"]
    assert client.post(f"{P}/registro/reenviar", json={"verificacion": "x" * 20}).status_code == 404


def test_sms_con_twilio(client, monkeypatch):
    llamadas = []

    def falso(ruta, campos):
        llamadas.append((ruta, campos))
        return {"status": "approved" if campos.get("Code") == "424242" else "pending"}

    monkeypatch.setattr(get_settings(), "sms_modo", "twilio")
    monkeypatch.setattr(sms, "_twilio", falso)
    v = client.post(f"{P}/registro", json=_datos()).json()
    assert v["modo"] == "twilio" and v["codigo_demo"] is None
    assert llamadas[0] == ("Verifications", {"To": "+56975658296", "Channel": "sms", "Locale": "es"})
    assert client.post(f"{P}/registro/confirmar", json={"verificacion": v["verificacion"], "codigo": "111111"}).status_code == 422
    r = client.post(f"{P}/registro/confirmar", json={"verificacion": v["verificacion"], "codigo": "424242"})
    assert r.status_code == 201 and llamadas[-1][0] == "VerificationCheck"


def test_twilio_sin_credenciales_responde_502(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "sms_modo", "twilio")
    r = client.post(f"{P}/registro", json=_datos())
    assert r.status_code == 502 and "Twilio" in r.json()["error"]["message"]


# ---------------------------------------------------------------- sesión (CU45)
def test_login_con_correo_o_rut_refresh_y_logout(client):
    _registrar(client)
    client.cookies.clear()
    assert client.post(f"{P}/auth/login", json={"usuario": "rep@example.com", "password": "Mala12345"}).status_code == 401
    h, me = _login(client, "11111111-1", CLAVE)  # RUT sin puntos
    assert me["nombre"] == "Carla Rojas Vidal"
    r = client.post(f"{P}/auth/refresh", headers=RH)
    assert r.status_code == 200
    assert client.post(f"{P}/auth/refresh").status_code == 403  # falta la cabecera anti-CSRF
    viejo = None
    for c in client.cookies.jar:
        viejo = c.value if c.name == "aca_portal" else viejo
    assert client.post(f"{P}/auth/logout", headers=RH).status_code == 204
    client.cookies.set("aca_portal", viejo, path="/api/v1/portal/auth")
    assert client.post(f"{P}/auth/refresh", headers=RH).status_code == 401


def test_tokens_del_portal_y_la_consola_no_se_mezclan(client, auth):
    h = _registrar(client)
    assert client.get(f"{API}/auth/me", headers=h).status_code == 401
    assert client.get(f"{P}/auth/me", headers=auth("admin")).status_code == 401
    assert client.get(f"{P}/auth/me").status_code == 401


def test_bloqueo_tras_intentos_fallidos(client):
    _registrar(client)
    for _ in range(5):
        client.post(f"{P}/auth/login", json={"usuario": "rep@example.com", "password": "Mala12345"})
    r = client.post(f"{P}/auth/login", json={"usuario": "rep@example.com", "password": CLAVE})
    assert r.status_code == 423


def test_reuso_de_refresh_revoca_las_sesiones(client):
    _registrar(client)
    viejo = next(c.value for c in client.cookies.jar if c.name == "aca_portal")
    assert client.post(f"{P}/auth/refresh", headers=RH).status_code == 200
    client.cookies.clear()
    client.cookies.set("aca_portal", viejo, path="/api/v1/portal/auth")
    assert client.post(f"{P}/auth/refresh", headers=RH).status_code == 401


# ---------------------------------------------------------------- planes y pagos (CU47 / CU49)
def test_planes_del_portal(client):
    h = _registrar(client)
    planes = {p["codigo_plan"]: p for p in client.get(f"{P}/planes", headers=h).json()}
    assert planes["platino"]["incluye_estado_tiempo_real"] and planes["proveedor"]["incluye_estado_tiempo_real"]
    assert not planes["dorado"]["incluye_estado_tiempo_real"] and planes["dorado"]["incluye_avisos_riesgo"]
    assert not planes["gratuito"]["incluye_avisos_riesgo"]


def test_pago_simulado_y_registro_del_residente(client):
    h = _registrar(client)
    assert client.get(f"{P}/representante/residentes", headers=h).json() == []
    r = client.post(f"{P}/representante/pagos", headers=h, json={"tipo": "alta", "codigo_plan": "platino"})
    o = r.json()
    assert o["resultado"] == "redirigir" and o["modo"] == "simulado" and o["url"].startswith("/portal/pago/simulado")
    # Rechazado: no crea suscripción
    r = client.post(f"{P}/pagos/{o['orden_compra']}/simulado", headers=h, json={"aprobar": False})
    assert r.json()["estado"] == "rechazada" and r.json()["id_suscripcion"] is None
    assert client.get(f"{P}/representante/residentes", headers=h).json() == []
    sid = _contratar(client, h, "platino")
    pago = client.get(f"{P}/pagos/{o['orden_compra']}").json()
    assert pago["estado"] == "rechazada"
    items = client.get(f"{P}/representante/residentes", headers=h).json()
    assert len(items) == 1 and items[0]["residente"] is None and items[0]["estado_suscripcion"] == "activa"
    # Residente: RUT inválido, claves distintas y luego correcto
    assert client.post(f"{P}/representante/suscripciones/{sid}/residente", headers=h,
                       json=_residente(rut="12.345.678-0")).status_code == 422
    assert client.post(f"{P}/representante/suscripciones/{sid}/residente", headers=h,
                       json=_residente(password2="Otra2026x")).status_code == 422
    assert client.post(f"{P}/representante/suscripciones/{sid}/residente", headers=h,
                       json=_residente(fecha_nacimiento=str(date.today()))).status_code == 422
    r = client.post(f"{P}/representante/suscripciones/{sid}/residente", headers=h, json=_residente())
    assert r.status_code == 201
    it = r.json()
    assert it["residente"]["nombre"] == "Hilda Pérez Soto" and it["residente"]["edad"] >= 80
    assert it["puede_ver_estado"] and it["recibe_avisos"]
    r = client.post(f"{P}/representante/suscripciones/{sid}/residente", headers=h, json=_residente(rut=RUT_RES2))
    assert r.status_code == 409 and r.json()["error"]["code"] == "ALREADY_ASSIGNED"
    with SessionLocal() as db:
        assert db.query(TransaccionPago).filter_by(estado="aprobada").count() == 1
        assert db.query(Suscripcion).filter_by(id_suscripcion=sid).one().id_paciente == it["residente"]["id_paciente"]


def test_residente_requiere_plan_pagado_y_dos_residentes(client):
    h = _registrar(client)
    sid = _contratar(client, h, "dorado")
    client.post(f"{P}/representante/suscripciones/{sid}/residente", headers=h, json=_residente())
    sid2 = _contratar(client, h, "gratuito")  # sin pasarela
    r = client.post(f"{P}/representante/suscripciones/{sid2}/residente", headers=h,
                    json=_residente(rut=RUT_RES, email="raul@example.com"))
    assert r.status_code == 409 and r.json()["error"]["code"] == "RUT_EXISTS"
    r = client.post(f"{P}/representante/suscripciones/{sid2}/residente", headers=h,
                    json=_residente(rut=RUT_RES2, primer_nombre="Raúl", email="raul@example.com"))
    assert r.status_code == 201
    items = client.get(f"{P}/representante/residentes", headers=h).json()
    assert [i["plan"]["codigo_plan"] for i in items] == ["dorado", "gratuito"]
    assert [i["puede_ver_estado"] for i in items] == [False, False] and [i["recibe_avisos"] for i in items] == [True, False]
    otro = _registrar(client, email="otro@example.com", rut=_rut_valido(13131313))
    assert client.post(f"{P}/representante/suscripciones/{sid}/residente", headers=otro,
                       json=_residente(rut=_rut_valido(14141414), email="x@example.com")).status_code == 404


def test_cambiar_renovar_y_cancelar_plan(client):
    h, sid, pid = _familia(client, "dorado")
    r = client.post(f"{P}/representante/pagos", headers=h, json={"tipo": "cambio", "codigo_plan": "dorado", "id_suscripcion": sid})
    assert r.status_code == 409 and r.json()["error"]["code"] == "NO_CHANGE"
    r = client.post(f"{P}/representante/pagos", headers=h, json={"tipo": "cambio", "codigo_plan": "platino", "id_suscripcion": sid})
    o = r.json()
    client.post(f"{P}/pagos/{o['orden_compra']}/simulado", headers=h, json={"aprobar": True})
    assert client.get(f"{P}/representante/residentes", headers=h).json()[0]["plan"]["codigo_plan"] == "platino"
    r = client.post(f"{P}/representante/pagos", headers=h, json={"tipo": "renovacion", "codigo_plan": "platino", "id_suscripcion": sid})
    client.post(f"{P}/pagos/{r.json()['orden_compra']}/simulado", headers=h, json={"aprobar": False})
    with SessionLocal() as db:
        assert db.query(TransaccionPago).filter_by(estado="rechazada", id_suscripcion=sid).count() == 1
        fin = db.get(Suscripcion, sid).fin_periodo
    r = client.post(f"{P}/representante/pagos", headers=h, json={"tipo": "renovacion", "codigo_plan": "platino", "id_suscripcion": sid})
    client.post(f"{P}/pagos/{r.json()['orden_compra']}/simulado", headers=h, json={"aprobar": True})
    with SessionLocal() as db:
        assert db.get(Suscripcion, sid).fin_periodo == fin + timedelta(days=30)
    # Bajar a gratuito no pasa por la pasarela
    r = client.post(f"{P}/representante/pagos", headers=h, json={"tipo": "cambio", "codigo_plan": "gratuito", "id_suscripcion": sid})
    assert r.json()["resultado"] == "listo"
    r = client.post(f"{P}/representante/pagos", headers=h, json={"tipo": "renovacion", "codigo_plan": "gratuito", "id_suscripcion": sid})
    assert r.status_code == 409
    r = client.post(f"{P}/representante/suscripciones/{sid}/cancelar", headers=h, json={"motivo": "Ya no lo necesitamos"})
    assert r.status_code == 200 and r.json()["estado_suscripcion"] == "cancelada"
    assert client.post(f"{P}/representante/suscripciones/{sid}/cancelar", headers=h, json={"motivo": "otra vez"}).status_code == 409
    r = client.post(f"{P}/representante/pagos", headers=h, json={"tipo": "cambio", "codigo_plan": "platino", "id_suscripcion": sid})
    assert r.status_code == 409
    assert client.get(f"{P}/representante/residentes/{pid}/estado", headers=h).status_code == 403
    # Contratar de nuevo para el mismo residente
    r = client.post(f"{P}/representante/pagos", headers=h, json={"tipo": "alta", "codigo_plan": "proveedor", "id_paciente": pid})
    client.post(f"{P}/pagos/{r.json()['orden_compra']}/simulado", headers=h, json={"aprobar": True})
    items = client.get(f"{P}/representante/residentes", headers=h).json()
    assert len(items) == 1 and items[0]["plan"]["codigo_plan"] == "proveedor" and items[0]["puede_ver_estado"]
    r = client.post(f"{P}/representante/pagos", headers=h, json={"tipo": "alta", "codigo_plan": "dorado", "id_paciente": pid})
    assert r.status_code == 409 and r.json()["error"]["code"] == "ALREADY_SUBSCRIBED"
    assert client.post(f"{P}/representante/pagos", headers=h, json={"tipo": "renovacion", "codigo_plan": "dorado"}).status_code == 422
    assert client.post(f"{P}/representante/pagos", headers=h, json={"tipo": "alta", "codigo_plan": "nada"}).status_code == 404


def test_webpay_flujo_completo(client, monkeypatch):
    """Webpay Plus: crear → el navegador paga → retorno con token_ws → commit. También anulación y rechazo."""
    monkeypatch.setattr(get_settings(), "pagos_modo", "webpay")
    monkeypatch.setattr(get_settings(), "frontend_url", "https://agecare-admin.onrender.com")
    creadas, respuestas = [], {}

    def crear(orden, sesion, monto, retorno):
        creadas.append((orden, sesion, monto, retorno))
        return {"token": f"tok{len(creadas):040d}", "url": "https://webpay3gint.transbank.cl/webpayserver/initTransaction"}

    def confirmar(token):
        return respuestas[token]

    monkeypatch.setattr(webpay, "crear", crear)
    monkeypatch.setattr(webpay, "confirmar", confirmar)
    h = _registrar(client)
    o = client.post(f"{P}/representante/pagos", headers=h, json={"tipo": "alta", "codigo_plan": "platino"}).json()
    assert o["modo"] == "webpay" and o["token"] == f"tok{1:040d}" and o["url"].startswith("https://webpay3gint")
    assert creadas[0][2] == 10000 and creadas[0][3] == "https://agecare-admin.onrender.com/api/v1/portal/pagos/webpay/retorno"
    respuestas[o["token"]] = {"vci": "TSY", "amount": 10000, "status": "AUTHORIZED", "buy_order": o["orden_compra"],
                              "card_detail": {"card_number": "6623"}, "authorization_code": "1213",
                              "payment_type_code": "VN", "response_code": 0}
    r = client.get(f"{P}/pagos/webpay/retorno", params={"token_ws": o["token"]}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].endswith(f"/portal/pago/resultado?orden={o['orden_compra']}")
    pago = client.get(f"{P}/pagos/{o['orden_compra']}").json()
    assert pago["estado"] == "aprobada" and pago["tarjeta"] == "6623" and pago["tipo_pago"] == "Crédito"
    assert pago["requiere_residente"]
    respuestas[o["token"]] = {"status": "FAILED", "response_code": -1}  # una recarga no vuelve a confirmar
    client.get(f"{P}/pagos/webpay/retorno", params={"token_ws": o["token"]}, follow_redirects=False)
    assert client.get(f"{P}/pagos/{o['orden_compra']}").json()["estado"] == "aprobada"
    # Rechazo (POST como en versiones antiguas de la API)
    o2 = client.post(f"{P}/representante/pagos", headers=h, json={"tipo": "alta", "codigo_plan": "dorado"}).json()
    respuestas[o2["token"]] = {"status": "FAILED", "response_code": -1, "buy_order": o2["orden_compra"], "amount": 1000}
    r = client.post(f"{P}/pagos/webpay/retorno", content=f"token_ws={o2['token']}",
                    headers={"Content-Type": "application/x-www-form-urlencoded"}, follow_redirects=False)
    assert r.status_code == 303 and client.get(f"{P}/pagos/{o2['orden_compra']}").json()["estado"] == "rechazada"
    # Anulación por el usuario (TBK_TOKEN por POST en integración) y tiempo agotado
    o3 = client.post(f"{P}/representante/pagos", headers=h, json={"tipo": "alta", "codigo_plan": "dorado"}).json()
    client.post(f"{P}/pagos/webpay/retorno", follow_redirects=False,
                content=f"TBK_TOKEN={o3['token']}&TBK_ORDEN_COMPRA={o3['orden_compra']}&TBK_ID_SESION=u1",
                headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert client.get(f"{P}/pagos/{o3['orden_compra']}").json()["estado"] == "anulada"
    o4 = client.post(f"{P}/representante/pagos", headers=h, json={"tipo": "alta", "codigo_plan": "dorado"}).json()
    client.get(f"{P}/pagos/webpay/retorno", params={"TBK_ORDEN_COMPRA": o4["orden_compra"], "TBK_ID_SESION": "u1"},
               follow_redirects=False)
    assert "tiempo" in client.get(f"{P}/pagos/{o4['orden_compra']}").json()["detalle"]
    # Monto alterado: no se acepta aunque Webpay diga AUTHORIZED
    o5 = client.post(f"{P}/representante/pagos", headers=h, json={"tipo": "alta", "codigo_plan": "dorado"}).json()
    respuestas[o5["token"]] = {"status": "AUTHORIZED", "response_code": 0, "buy_order": o5["orden_compra"], "amount": 1}
    client.get(f"{P}/pagos/webpay/retorno", params={"token_ws": o5["token"]}, follow_redirects=False)
    assert client.get(f"{P}/pagos/{o5['orden_compra']}").json()["estado"] == "rechazada"
    assert client.post(f"{P}/pagos/{o5['orden_compra']}/simulado", headers=h, json={"aprobar": True}).status_code == 409
    r = client.get(f"{P}/pagos/webpay/retorno", params={"token_ws": "desconocido"}, follow_redirects=False)
    assert r.headers["location"].endswith("/portal/pago/resultado")
    assert client.get(f"{P}/pagos/NOEXISTE").status_code == 404


def test_webpay_caido_y_errores_de_commit(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "pagos_modo", "webpay")

    def caido(*a):
        raise webpay.ErrorWebpay("No se pudo conectar con Transbank: timeout")

    monkeypatch.setattr(webpay, "crear", caido)
    h = _registrar(client)
    r = client.post(f"{P}/representante/pagos", headers=h, json={"tipo": "alta", "codigo_plan": "platino"})
    assert r.status_code == 502 and r.json()["error"]["code"] == "GATEWAY_ERROR"
    with SessionLocal() as db:
        assert db.query(OrdenPago).one().estado == "error"
    monkeypatch.setattr(webpay, "crear", lambda *a: {"token": "t" * 64, "url": "https://webpay3gint.transbank.cl/x"})
    monkeypatch.setattr(webpay, "confirmar", caido)
    o = client.post(f"{P}/representante/pagos", headers=h, json={"tipo": "alta", "codigo_plan": "platino"}).json()
    client.get(f"{P}/pagos/webpay/retorno", params={"token_ws": o["token"]}, follow_redirects=False)
    assert client.get(f"{P}/pagos/{o['orden_compra']}").json()["estado"] == "error"


def test_cliente_webpay_arma_la_peticion(monkeypatch):
    """La llamada real a Transbank: cabeceras de integración, cuerpo y ruta v1.2."""
    import json as _json
    import urllib.request

    vistas = []

    class Resp:
        def __init__(self, cuerpo):
            self.cuerpo = cuerpo

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return self.cuerpo

    def urlopen(req, timeout):
        vistas.append(req)
        return Resp(_json.dumps({"token": "abc", "url": "https://webpay3gint.transbank.cl/webpayserver/initTransaction"}).encode())

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    r = webpay.crear("ACA123", "u1", 5000, "https://x/retorno")
    req = vistas[0]
    assert r["token"] == "abc" and req.get_method() == "POST"
    assert req.full_url == "https://webpay3gint.transbank.cl/rswebpaytransaction/api/webpay/v1.2/transactions"
    assert req.headers["Tbk-api-key-id"] == "597055555532" and _json.loads(req.data)["amount"] == 5000
    webpay.confirmar("abc")
    assert vistas[1].get_method() == "PUT" and vistas[1].full_url.endswith("/transactions/abc")
    webpay.estado("abc")
    assert vistas[2].get_method() == "GET"
    assert webpay.aprobado({"response_code": 0, "status": "AUTHORIZED"})
    assert not webpay.aprobado({"response_code": 0, "status": "FAILED"})


# ---------------------------------------------------------------- ficha del cuidador y avisos (CU50 / CU53)
def test_cuidador_riesgoso_avisa_por_whatsapp_y_en_el_portal(client, auth):
    h, sid, pid = _familia(client, "platino")
    hc = _cuidador(client, auth, pid)
    assert client.get(f"{P}/cuidador/residentes", headers=hc).json()[0]["ultimo_estado"] is None
    r = client.get(f"{P}/representante/residentes/{pid}/estado", headers=h).json()
    assert r["actual"] is None and r["actualizar_cada_seg"] == 15
    r = client.post(f"{P}/cuidador/residentes/{pid}/ficha", headers=hc, json={"estado": "normal", "observacion": "Tomó desayuno."})
    assert r.status_code == 201 and r.json()["avisos_portal"] == 0
    r = client.post(f"{P}/cuidador/residentes/{pid}/ficha", headers=hc,
                    json={"estado": "riesgoso", "observacion": "Mareo fuerte y\npresión baja; se llamó al médico."})
    assert r.status_code == 201
    f = r.json()
    assert f["avisos_portal"] == 1 and f["avisos_whatsapp"] == 1 and "Riesgoso" in f["mensaje"]
    est = client.get(f"{P}/representante/residentes/{pid}/estado", headers=h).json()
    assert est["actual"]["etiqueta"] == "Riesgoso" and est["actual"]["cuidador"] == "Juan Muñoz"
    assert len(est["historial"]) == 2
    n = client.get(f"{P}/notificaciones", headers=h).json()
    assert n["items"][0]["tipo"] == "estado_riesgoso" and "Mareo" in n["items"][0]["cuerpo"]
    assert client.post(f"{P}/notificaciones/leer", headers=h).json()["sin_leer"] == 0
    with SessionLocal() as db:
        m = db.query(MensajeWhatsapp).one()
        assert m.telefono == "+56975658296" and "estado Riesgoso registrado por la cuidadora" in m.contenido
        assert "\n" not in m.contenido  # Meta no acepta saltos de línea en las variables
    hist = client.get(f"{P}/cuidador/residentes/{pid}/historial", headers=hc).json()
    assert [x["estado"] for x in hist] == ["riesgoso", "normal"]
    # Un cuidador no ve residentes ajenos y un representante no registra fichas
    assert client.post(f"{P}/cuidador/residentes/{pid + 99}/ficha", headers=hc,
                       json={"estado": "normal", "observacion": "x" * 5}).status_code == 404
    assert client.post(f"{P}/cuidador/residentes/{pid}/ficha", headers=h,
                       json={"estado": "normal", "observacion": "x" * 5}).status_code == 403


def test_plan_dorado_avisa_pero_no_muestra_estado_y_gratuito_no_avisa(client, auth):
    h, sid, pid = _familia(client, "dorado")
    hc = _cuidador(client, auth, pid)
    r = client.get(f"{P}/representante/residentes/{pid}/estado", headers=h)
    assert r.status_code == 403 and r.json()["error"]["code"] == "PLAN_REQUIRED" and "Dorado" in r.json()["error"]["message"]
    f = client.post(f"{P}/cuidador/residentes/{pid}/ficha", headers=hc,
                    json={"estado": "riesgoso", "observacion": "Fiebre alta"}).json()
    assert f["avisos_portal"] == 1 and f["avisos_whatsapp"] == 1
    client.post(f"{P}/representante/pagos", headers=h, json={"tipo": "cambio", "codigo_plan": "gratuito", "id_suscripcion": sid})
    f = client.post(f"{P}/cuidador/residentes/{pid}/ficha", headers=hc,
                    json={"estado": "riesgoso", "observacion": "Fiebre alta otra vez"}).json()
    assert f["avisos_portal"] == 0 and f["avisos_whatsapp"] == 0 and "no incluye" in f["mensaje"]
    with SessionLocal() as db:
        assert db.query(MensajeWhatsapp).filter_by(estado="omitido").count() == 1
    f = client.post(f"{P}/cuidador/residentes/{pid}/ficha", headers=hc, json={"estado": "alerta", "observacion": "Cansada"}).json()
    assert f["registro"]["etiqueta"] == "Alerta"


def test_evento_de_la_plataforma_tambien_avisa_en_el_portal(client, auth):
    h, sid, pid = _familia(client, "platino")
    r = client.post(f"{API}/operacion/eventos-salud", headers=auth("soporte"), json={"id_paciente": pid, "tipo": "caida"})
    assert r.status_code == 201
    n = client.get(f"{P}/notificaciones", headers=h).json()["items"][0]
    assert n["tipo"] == "alerta_salud" and "caída" in n["cuerpo"]


def test_whatsapp_desde_el_portal(client):
    h = _registrar(client, acepta_whatsapp=False)
    assert not client.get(f"{P}/auth/me", headers=h).json()["whatsapp_habilitado"]
    r = client.put(f"{P}/me/whatsapp", headers=h, json={"habilitado": True})
    assert r.json()["whatsapp_habilitado"]
    assert not client.put(f"{P}/me/whatsapp", headers=h, json={"habilitado": False}).json()["whatsapp_habilitado"]


# ---------------------------------------------------------------- residente (CU51 / CU52)
def test_residente_ve_contenidos_y_pide_ayuda(client, auth):
    h, sid, pid = _familia(client)
    hr, me = _login(client, RUT_RES, "Hilda2026")  # el residente entra con su RUT
    assert me["vistas"] == ["residente"]
    he = auth("editor")
    ev = client.post(f"{API}/contenidos", headers=he, json={"tipo": "evento", "titulo": "Taller de memoria",
                                                         "cuerpo": "Juegos y ejercicios para la memoria.", "lugar": "Sala común"})
    assert ev.status_code == 422  # un evento necesita fecha
    manana = (utcnow() + timedelta(days=1)).isoformat()
    ev = client.post(f"{API}/contenidos", headers=he, json={"tipo": "evento", "titulo": "Taller de memoria", "lugar": "Sala común",
                                                         "cuerpo": "Juegos y ejercicios para la memoria.", "fecha_evento": manana})
    assert ev.status_code == 201 and ev.json()["lugar"] == "Sala común"
    client.post(f"{API}/contenidos/{ev.json()['id_contenido']}/publicar", headers=he, json={})
    ch = client.post(f"{API}/contenidos", headers=he, json={"tipo": "chiste", "titulo": "El colmo",
                                                         "cuerpo": "¿Cuál es el colmo de un jardinero? Que lo dejen plantado."})
    client.post(f"{API}/contenidos/{ch.json()['id_contenido']}/publicar", headers=he, json={})
    client.post(f"{API}/contenidos", headers=he, json={"tipo": "noticia", "titulo": "Borrador", "cuerpo": "No se publica aún."})
    with SessionLocal() as db:  # un evento ya pasado no se muestra
        db.add(Contenido(tipo="evento", titulo="Evento antiguo", cuerpo="Ya ocurrió hace tiempo.", estado="publicado",
                         fecha_publicacion=utcnow(), fecha_evento=utcnow() - timedelta(days=5), lugar="Patio"))
        db.commit()
    todo = client.get(f"{P}/contenidos", headers=hr).json()
    assert {c["titulo"] for c in todo} == {"Taller de memoria", "El colmo"}
    assert [c["titulo"] for c in client.get(f"{P}/contenidos", headers=hr, params={"tipo": "evento"}).json()] == ["Taller de memoria"]
    ini = client.get(f"{P}/residente/inicio", headers=hr).json()
    assert ini["nombre"] == "Hilda" and ini["representantes"] == ["Carla Rojas Vidal"]
    r = client.post(f"{P}/ayuda", headers=hr, json={"categoria": "otros", "asunto": "No veo bien la letra",
                                                    "descripcion": "Quisiera que la letra fuera más grande."})
    assert r.status_code == 201
    t = client.get(f"{API}/soporte/tickets/#{r.json()['numero']}".replace("#", "%23"), headers=auth("soporte")).json()
    assert t["canal"] == "app" and t["solicitante"]["nombre"] == "Hilda Pérez Soto" and t["paciente"]["nombre"] == "Hilda Pérez Soto"
    # El residente no paga ni cambia planes
    assert client.get(f"{P}/representante/residentes", headers=hr).status_code == 403
    assert client.post(f"{P}/representante/pagos", headers=hr, json={"tipo": "alta", "codigo_plan": "platino"}).status_code == 403


def test_olvide_mi_contrasena_crea_ticket_y_soporte_la_restablece(client, auth):
    h, sid, pid = _familia(client)
    msg = client.post(f"{P}/auth/olvide", json={"usuario": "hilda@example.com", "detalle": "No recuerdo la clave"}).json()
    assert "soporte te contactará" in msg["mensaje"]
    assert client.post(f"{P}/auth/olvide", json={"usuario": "noexiste@example.com"}).json() == msg  # misma respuesta
    client.post(f"{P}/auth/olvide", json={"usuario": RUT_RES})  # repetido en 24 h: no duplica
    with SessionLocal() as db:
        t = db.query(Ticket).one()
        assert t.canal == "app" and t.codigo_categoria == "acceso_cuenta" and t.prioridad == "alta"
        assert t.asunto.startswith("Olvidé mi contraseña") and "No recuerdo la clave" in t.descripcion
        id_res = db.query(UsuarioApp).filter_by(email="hilda@example.com").one().id_usuario
    r = client.post(f"{API}/usuarios/{id_res}/restablecer-password", headers=auth("soporte"),
                    json={"motivo": f"Ticket #{t.numero}, identidad validada por teléfono"})
    assert r.status_code == 200
    temporal = r.json()["password_temporal"]
    assert client.post(f"{P}/auth/login", json={"usuario": RUT_RES, "password": "Hilda2026"}).status_code == 401
    hr, me = _login(client, RUT_RES, temporal)
    assert me["debe_cambiar_password"]
    r = client.get(f"{P}/contenidos", headers=hr)
    assert r.status_code == 403 and r.json()["error"]["code"] == "PASSWORD_CHANGE_REQUIRED"
    assert client.post(f"{P}/auth/cambiar-password", headers=hr,
                       json={"actual": "mala", "password": "Nueva2026", "password2": "Nueva2026"}).status_code == 422
    assert client.post(f"{P}/auth/cambiar-password", headers=hr,
                       json={"actual": temporal, "password": temporal, "password2": temporal}).status_code in (422,)
    client.post(f"{P}/auth/cambiar-password", headers=hr, json={"actual": temporal, "password": "Nueva2026", "password2": "Nueva2026"})
    assert client.get(f"{P}/contenidos", headers=hr).status_code == 200
    assert client.post(f"{API}/usuarios/{id_res}/restablecer-password", headers=auth("analista"),
                       json={"motivo": "sin permiso"}).status_code == 403


def test_ayuda_limite_por_hora(client):
    h = _registrar(client)
    for i in range(5):
        assert client.post(f"{P}/ayuda", headers=h, json={"asunto": f"Consulta {i}", "descripcion": "Necesito ayuda con algo."}).status_code == 201
    assert client.post(f"{P}/ayuda", headers=h, json={"asunto": "Una más", "descripcion": "Necesito ayuda con algo."}).status_code == 429


# ---------------------------------------------------------------- consola (CU54 / CU55)
def test_consola_crea_representante_y_residente(client, auth):
    hs = auth("soporte")
    r = client.post(f"{API}/usuarios", headers=hs, json={
        "perfil": "representante", "rut": _rut_valido(16161616), "nombres": "Pedro", "primer_apellido": "Soto",
        "email": "pedro@example.com", "telefono": "912345678", "whatsapp_habilitado": True})
    assert r.status_code == 201, r.text
    rep, temporal = r.json()["usuario"], r.json()["password_temporal"]
    assert rep["vistas_portal"] == ["representante"] and rep["debe_cambiar_password"] and rep["telefono"] == "+56912345678"
    r = client.post(f"{API}/usuarios", headers=hs, json={
        "perfil": "residente", "rut": RUT_RES, "nombres": "Marta", "primer_apellido": "Soto", "email": "marta@example.com",
        "fecha_nacimiento": "1945-01-10", "id_representante": rep["id_usuario"], "codigo_plan": "platino"})
    assert r.status_code == 201, r.text
    res = r.json()
    assert res["usuario"]["vistas_portal"] == ["residente"] and res["usuario"]["id_paciente_propio"]
    pid = res["usuario"]["id_paciente_propio"]
    ops = client.get(f"{API}/usuarios/residentes/opciones", headers=hs, params={"q": "marta"}).json()
    assert ops[0]["plan"] == "platino" and ops[0]["representantes"] == ["Pedro Soto"]
    assert client.get(f"{API}/usuarios/residentes/opciones", headers=hs, params={"q": RUT_RES}).json()[0]["id_paciente"] == pid
    hp, me = _login(client, "pedro@example.com", temporal)
    assert client.get(f"{P}/representante/residentes", headers=hp).status_code == 403  # primero cambia la clave
    client.post(f"{P}/auth/cambiar-password", headers=hp, json={"actual": temporal, "password": "Pedro2026", "password2": "Pedro2026"})
    items = client.get(f"{P}/representante/residentes", headers=hp).json()
    assert items[0]["plan"]["codigo_plan"] == "platino" and items[0]["residente"]["nombre"] == "Marta Soto"
    assert items[0]["puede_ver_estado"]
    hm, me = _login(client, RUT_RES, res["password_temporal"])
    assert me["vistas"] == ["residente"] and me["debe_cambiar_password"]


def test_consola_asigna_y_quita_residentes(client, auth):
    h, sid, pid = _familia(client)
    hs = auth("soporte")
    r = client.post(f"{API}/usuarios", headers=hs, json={"perfil": "cuidador", "rut": RUT_CUI, "nombres": "Juan",
                                                       "primer_apellido": "Muñoz", "email": "juan@example.com"})
    cid = r.json()["usuario"]["id_usuario"]
    r = client.post(f"{API}/usuarios/{cid}/residentes", headers=hs, json={"id_paciente": pid})
    assert r.status_code == 201 and r.json()["membresias"][0]["rol_en_circulo"] == "cuidadora"
    assert client.post(f"{API}/usuarios/{cid}/residentes", headers=hs, json={"id_paciente": pid}).status_code == 409
    r = client.delete(f"{API}/usuarios/{cid}/residentes/{pid}", headers=hs)
    assert r.json()["membresias"][0]["estado"] == "revocado"
    assert client.delete(f"{API}/usuarios/{cid}/residentes/{pid}", headers=hs).status_code == 404
    assert client.post(f"{API}/usuarios/{cid}/residentes", headers=hs, json={"id_paciente": pid}).status_code == 201
    with SessionLocal() as db:
        id_res = db.query(UsuarioApp).filter_by(email="hilda@example.com").one().id_usuario
    r = client.post(f"{API}/usuarios/{id_res}/residentes", headers=hs, json={"id_paciente": pid})
    assert r.status_code == 409 and r.json()["error"]["code"] == "INVALID_PROFILE"
    r = client.post(f"{API}/usuarios", headers=hs, json={"perfil": "residente", "rut": RUT_RES2, "nombres": "Luis",
                                                       "primer_apellido": "Paz", "email": "luis@example.com"})
    assert r.status_code == 422  # falta fecha de nacimiento y representante
    r = client.post(f"{API}/usuarios", headers=hs, json={"perfil": "residente", "rut": RUT_RES2, "nombres": "Luis",
                                                       "primer_apellido": "Paz", "email": "luis@example.com",
                                                       "fecha_nacimiento": "1940-02-02", "id_representante": cid})
    assert r.status_code == 422 and "no es un representante" in r.json()["error"]["message"]
    assert client.post(f"{API}/usuarios", headers=auth("analista"), json={}).status_code in (403, 422)
    usuarios = client.get(f"{API}/usuarios", headers=hs, params={"q": RUT_CUI}).json()
    assert usuarios["total"] == 1 and usuarios["items"][0]["rut"] == "15.555.553-K"


def test_usuario_sin_vista_no_entra_al_portal(client, auth):
    with SessionLocal() as db:
        from app.models import UsuarioPerfil
        from app.security import hash_password
        u = UsuarioApp(nombre="Dra. Paula", email="paula@example.com", password_hash=hash_password("Medica2026"))
        db.add(u)
        db.flush()
        db.add(UsuarioPerfil(id_usuario=u.id_usuario, codigo_perfil="medico"))
        db.commit()
    r = client.post(f"{P}/auth/login", json={"usuario": "paula@example.com", "password": "Medica2026"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "NO_PORTAL_VIEW"


@pytest.mark.parametrize("estado", ["desactivada"])
def test_cuenta_desactivada_no_entra(client, auth, estado):
    _registrar(client)
    with SessionLocal() as db:
        uid = db.query(UsuarioApp).filter_by(email="rep@example.com").one().id_usuario
    client.patch(f"{API}/usuarios/{uid}/estado", headers=auth("soporte"), json={"estado_cuenta": estado, "motivo": "Prueba de cuenta"})
    r = client.post(f"{P}/auth/login", json={"usuario": "rep@example.com", "password": CLAVE})
    assert r.status_code == 403 and r.json()["error"]["code"] == "ACCOUNT_DISABLED"
    with SessionLocal() as db:
        assert db.query(NotificacionApp).count() == 1


def test_planificador_anula_ordenes_abandonadas(client):
    from app.planificador import anular_ordenes_abandonadas
    h = _registrar(client)
    o = client.post(f"{P}/representante/pagos", headers=h, json={"tipo": "alta", "codigo_plan": "platino"}).json()
    with SessionLocal() as db:
        assert anular_ordenes_abandonadas(db) == 0
        x = db.query(OrdenPago).one()
        x.fecha_creacion = utcnow() - timedelta(minutes=31)
        db.commit()
        assert anular_ordenes_abandonadas(db) == 1
    assert client.get(f"{P}/pagos/{o['orden_compra']}").json()["estado"] == "anulada"


def test_cliente_twilio_arma_la_peticion(monkeypatch):
    import io
    import json as _json
    import urllib.error
    import urllib.request

    st = get_settings()
    for k, v in (("twilio_account_sid", "AC123"), ("twilio_auth_token", "tok"), ("twilio_verify_sid", "VA999")):
        monkeypatch.setattr(st, k, v)
    vistas = []

    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def urlopen(req, timeout):
        vistas.append(req)
        if req.full_url.endswith("VerificationCheck"):
            raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, io.BytesIO(b"{}"))
        return Resp(_json.dumps({"status": "pending"}).encode())

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    assert sms._twilio("Verifications", {"To": "+56911112222", "Channel": "sms"})["status"] == "pending"
    assert vistas[0].full_url == "https://verify.twilio.com/v2/Services/VA999/Verifications"
    assert vistas[0].headers["Authorization"].startswith("Basic ")
    assert sms._twilio("VerificationCheck", {"To": "+56911112222", "Code": "1"}) == {"status": "expired"}


def test_consola_ve_los_pagos_del_portal(client, auth):
    h = _registrar(client)
    _contratar(client, h, "platino")
    r = client.get(f"{API}/comercial/ordenes-portal", headers=auth("analista")).json()
    assert r["total"] == 1 and r["items"][0]["estado"] == "aprobada" and r["items"][0]["representante"] == "Carla Rojas Vidal"
    subs = client.get(f"{API}/comercial/suscripciones", headers=auth("admin")).json()["items"]
    assert subs[0]["plan"] == "Platino" and subs[0]["residente"] is None
    assert client.get(f"{API}/comercial/ordenes-portal", headers=auth("soporte")).status_code == 403


def test_legales_publicos(client):
    assert client.get(f"{P}/legales").json() == []  # sin versiones publicadas en la base de pruebas
