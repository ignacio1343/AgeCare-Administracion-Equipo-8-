"""Avisos de salud por WhatsApp al familiar (CU41 a CU43)."""
import hashlib
import hmac
import json
from datetime import timedelta

import pytest

from app import whatsapp as wa
from app.config import get_settings
from app.db import SessionLocal, utcnow
from app.models import (CuentaCliente, MembresiaCirculo, MensajeWhatsapp, Paciente, ParametroSistema, Suscripcion,
                        UsuarioApp, UsuarioPerfil)

from .conftest import API


def _escenario(plan="platino", consentimiento=True, telefono="+56912345678"):
    """Paciente con un familiar (titular de la cuenta con el plan indicado) y una cuidadora."""
    with SessionLocal() as db:
        fam = db.query(UsuarioApp).filter_by(email="ana@example.com").one()
        fam.telefono, fam.whatsapp_habilitado = telefono, consentimiento
        cuid = UsuarioApp(nombre="Rosa Cuidadora", email="rosa@example.com", telefono="+56987654321", whatsapp_habilitado=True)
        p = Paciente(nombre="Humberto Castro")
        db.add_all([cuid, p])
        db.flush()
        db.add_all([UsuarioPerfil(id_usuario=fam.id_usuario, codigo_perfil="familiar"),
                    MembresiaCirculo(id_usuario=fam.id_usuario, id_paciente=p.id_paciente, rol_en_circulo="familiar"),
                    MembresiaCirculo(id_usuario=cuid.id_usuario, id_paciente=p.id_paciente, rol_en_circulo="cuidadora")])
        if plan:
            c = CuentaCliente(id_usuario=fam.id_usuario, tipo_cuenta="familia", nombre="Familia Castro",
                              email_facturacion="ana@example.com")
            db.add(c)
            db.flush()
            db.add(Suscripcion(id_cuenta=c.id_cuenta, codigo_plan=plan, fin_periodo=utcnow() + timedelta(days=30)))
        db.commit()
        return p.id_paciente, fam.id_usuario


def _evento(client, h, pid, **kw):
    return client.post(f"{API}/operacion/eventos-salud", headers=h, json={"id_paciente": pid, **kw})


# ---------------------------------------------------------------- unitarias
@pytest.mark.parametrize("entrada,esperado", [("+56 9 1234 5678", "+56912345678"), ("912345678", "+56912345678"),
                                             ("56912345678", "+56912345678"), ("+44 7700 900123", "+447700900123"),
                                             ("1234", None), ("", None)])
def test_normalizar_telefono(entrada, esperado):
    assert wa.normalizar_telefono(entrada) == esperado
    assert wa.enmascarar("+56912345678") == "+569 •••• 5678"


def test_semaforo_de_lecturas(client):
    with SessionLocal() as db:
        assert wa.nivel_de_lectura(db, "saturacion_o2", 97) == "verde"
        assert wa.nivel_de_lectura(db, "saturacion_o2", 92) == "amarillo"
        assert wa.nivel_de_lectura(db, "saturacion_o2", 85) == "rojo"
        assert wa.nivel_de_lectura(db, "frecuencia_cardiaca", 135) == "rojo"
        assert wa.nivel_de_lectura(db, "no_existe", 1) is None


# ---------------------------------------------------------------- flujo completo
def test_signo_vital_rojo_avisa_solo_al_familiar(client, auth):
    pid, uid = _escenario()
    r = _evento(client, auth("soporte"), pid, tipo="vital", signo_vital="saturacion_o2", valor=86)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["nivel"] == "rojo" and body["severidad"] == "critica"
    assert len(body["avisos"]) == 1  # la cuidadora no es «familiar»
    aviso = body["avisos"][0]
    assert aviso["telefono"] == "+569 •••• 5678"  # la consola nunca muestra el número completo
    assert "Humberto Castro" in aviso["contenido"] and "saturación de oxígeno 86 %" in aviso["contenido"]
    with SessionLocal() as db:  # la tarea en segundo plano ya lo envió (modo simulado)
        m = db.get(MensajeWhatsapp, aviso["id_mensaje"])
        assert m.estado == "enviado" and m.id_mensaje_proveedor.startswith("wamid.SIM") and m.intentos == 1
        assert m.alerta.signo_vital == "saturacion_o2" and m.alerta.nivel_semaforo == "rojo"


def test_verde_no_alerta_y_amarillo_no_avisa(client, auth):
    pid, _ = _escenario()
    h = auth("soporte")
    r = _evento(client, h, pid, tipo="vital", signo_vital="temperatura", valor=36.6).json()
    assert r["id_alerta"] is None and r["nivel"] == "verde"
    r = _evento(client, h, pid, tipo="vital", signo_vital="temperatura", valor=37.8).json()
    assert r["nivel"] == "amarillo" and r["severidad"] == "media" and r["avisos"] == []


def test_caida_y_sos_son_criticos_y_se_agrupan(client, auth):
    pid, _ = _escenario()
    h = auth("soporte")
    a1 = _evento(client, h, pid, tipo="caida").json()["avisos"][0]
    assert "posible caída detectada" in a1["contenido"]
    a2 = _evento(client, h, pid, tipo="sos").json()["avisos"][0]
    assert a2["estado"] == "omitido" and a2["motivo"].startswith("Agrupado")  # menos de 30 min: no se satura


@pytest.mark.parametrize("plan,consent,tel,motivo", [
    ("gratuito", True, "+56912345678", "no incluye avisos"),
    (None, True, "+56912345678", "sin suscripción"),
    ("platino", False, "+56912345678", "no ha autorizado"),
    ("platino", True, None, "no tiene un teléfono"),
])
def test_avisos_omitidos_quedan_con_motivo(client, auth, plan, consent, tel, motivo):
    pid, _ = _escenario(plan=plan, consentimiento=consent, telefono=tel)
    aviso = _evento(client, auth("soporte"), pid, tipo="sos").json()["avisos"][0]
    assert aviso["estado"] == "omitido" and motivo in aviso["motivo"]


def test_parametro_apagado_no_genera_avisos(client, auth):
    pid, _ = _escenario()
    with SessionLocal() as db:
        db.get(ParametroSistema, "whatsapp_activo").valor = "false"
        db.commit()
    r = _evento(client, auth("soporte"), pid, tipo="caida").json()
    assert r["severidad"] == "critica" and r["avisos"] == []


def test_reintentos_y_fallido_luego_reintento_manual(client, auth):
    pid, uid = _escenario(telefono="+56900000000")  # el simulador hace fallar los números terminados en 0000
    h = auth("soporte")
    aviso = _evento(client, h, pid, tipo="sos").json()["avisos"][0]
    with SessionLocal() as db:
        m = db.get(MensajeWhatsapp, aviso["id_mensaje"])
        assert m.estado == "pendiente" and m.intentos == 1 and m.proximo_intento > utcnow()  # espera 1 min
        for _ in range(2):  # el planificador reintenta cuando vence la espera
            m.proximo_intento = utcnow() - timedelta(seconds=1)
            db.commit()
            wa.procesar_pendientes(db)
            db.refresh(m)
        assert m.estado == "fallido" and m.intentos == 3 and "no tiene WhatsApp" in m.motivo
        db.get(UsuarioApp, uid).telefono = "+56912345678"
        db.commit()
    r = client.post(f"{API}/whatsapp/mensajes/{aviso['id_mensaje']}/reintentar", headers=h)
    assert r.status_code == 200
    with SessionLocal() as db:
        assert db.get(MensajeWhatsapp, aviso["id_mensaje"]).estado == "enviado"
    assert client.post(f"{API}/whatsapp/mensajes/{aviso['id_mensaje']}/reintentar", headers=h).status_code == 409


def test_simulador_marca_entregado_y_leido(client, auth):
    pid, _ = _escenario()
    aviso = _evento(client, auth("soporte"), pid, tipo="caida").json()["avisos"][0]
    with SessionLocal() as db:
        m = db.get(MensajeWhatsapp, aviso["id_mensaje"])
        m.fecha_envio = utcnow() - timedelta(minutes=1)
        db.commit()
        wa.procesar_pendientes(db)
        db.refresh(m)
        assert m.estado == "entregado" and m.fecha_entrega


# ---------------------------------------------------------------- Meta: envío real (mock) y webhook
def test_envio_meta_arma_la_plantilla(client, auth, monkeypatch):
    pid, _ = _escenario()
    st = get_settings()
    monkeypatch.setattr(st, "whatsapp_modo", "meta")
    monkeypatch.setattr(st, "whatsapp_token", "tok")
    monkeypatch.setattr(st, "whatsapp_phone_number_id", "123")
    enviados = []

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps({"messages": [{"id": "wamid.REAL1"}]}).encode()

    def fake_urlopen(req, timeout):
        enviados.append((req.full_url, req.headers, json.loads(req.data)))
        return Resp()

    monkeypatch.setattr(wa.urllib.request, "urlopen", fake_urlopen)
    _evento(client, auth("soporte"), pid, tipo="vital", signo_vital="frecuencia_cardiaca", valor=140)
    url, headers, cuerpo = enviados[0]
    assert url == "https://graph.facebook.com/v22.0/123/messages" and headers["Authorization"] == "Bearer tok"
    assert cuerpo["to"] == "56912345678" and cuerpo["type"] == "template"
    t = cuerpo["template"]
    assert t["name"] == "alerta_salud_familiar" and t["language"] == {"code": "es"}
    params = [p["text"] for p in t["components"][0]["parameters"]]
    assert params[0] == "Humberto Castro" and params[1] == "frecuencia cardíaca 140 lpm (fuera de rango)"


def test_meta_error_4xx_no_se_reintenta(client, auth, monkeypatch):
    import io
    import urllib.error
    pid, _ = _escenario()
    st = get_settings()
    monkeypatch.setattr(st, "whatsapp_modo", "meta")
    monkeypatch.setattr(st, "whatsapp_token", "tok")
    monkeypatch.setattr(st, "whatsapp_phone_number_id", "123")

    def falla(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 400, "Bad Request", {},
                                     io.BytesIO(b'{"error":{"message":"Template name does not exist","code":132001}}'))

    monkeypatch.setattr(wa.urllib.request, "urlopen", falla)
    aviso = _evento(client, auth("soporte"), pid, tipo="sos").json()["avisos"][0]
    with SessionLocal() as db:
        m = db.get(MensajeWhatsapp, aviso["id_mensaje"])
        assert m.estado == "fallido" and m.intentos == 1 and "132001" in m.motivo


def _firmar(cuerpo: bytes, secreto="app-secret"):
    return "sha256=" + hmac.new(secreto.encode(), cuerpo, hashlib.sha256).hexdigest()


def test_webhook_meta_firma_y_estados(client, auth, monkeypatch):
    monkeypatch.setattr(get_settings(), "whatsapp_app_secret", "app-secret")
    monkeypatch.setattr(get_settings(), "whatsapp_verify_token", "verifica")
    pid, _ = _escenario()
    aviso = _evento(client, auth("soporte"), pid, tipo="caida").json()["avisos"][0]
    with SessionLocal() as db:
        wamid = db.get(MensajeWhatsapp, aviso["id_mensaje"]).id_mensaje_proveedor
    # verificación de la suscripción del webhook
    r = client.get(f"{API}/whatsapp/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "verifica",
                                                       "hub.challenge": "42"})
    assert r.status_code == 200 and r.text == "42"
    assert client.get(f"{API}/whatsapp/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "x",
                                                          "hub.challenge": "42"}).status_code == 403

    def estado(status, ts):
        return json.dumps({"entry": [{"changes": [{"value": {"statuses": [{"id": wamid, "status": status,
                                                                            "timestamp": str(ts)}]}}]}]}).encode()
    leido = estado("read", 1790000100)
    assert client.post(f"{API}/whatsapp/webhook", content=leido,
                       headers={"X-Hub-Signature-256": "sha256=malo"}).status_code == 401
    assert client.post(f"{API}/whatsapp/webhook", content=leido,
                       headers={"X-Hub-Signature-256": _firmar(leido)}).json()["cambios"] == 1
    # un «delivered» que llega tarde no hace retroceder el estado
    tarde = estado("delivered", 1790000050)
    assert client.post(f"{API}/whatsapp/webhook", content=tarde,
                       headers={"X-Hub-Signature-256": _firmar(tarde)}).json()["cambios"] == 0
    with SessionLocal() as db:
        m = db.get(MensajeWhatsapp, aviso["id_mensaje"])
        assert m.estado == "leido" and m.fecha_lectura and m.fecha_entrega


# ---------------------------------------------------------------- consola, permisos e integración
def test_consentimiento_del_familiar_queda_en_auditoria(client, auth):
    _, uid = _escenario(consentimiento=False, telefono=None)
    h = auth("soporte")
    r = client.put(f"{API}/usuarios/{uid}/whatsapp", headers=h,
                   json={"telefono": "9 1234 5678", "whatsapp_habilitado": True, "motivo": "Autorizó por correo"})
    assert r.status_code == 200 and r.json()["telefono"] == "+56912345678" and r.json()["whatsapp_verificado"]
    r = client.put(f"{API}/usuarios/{uid}/whatsapp", headers=h,
                   json={"telefono": "123", "whatsapp_habilitado": True, "motivo": "Autorizó por correo"})
    assert r.status_code == 422
    log = client.get(f"{API}/auditoria", headers=auth("admin"), params={"accion": "usuario_app.whatsapp"}).json()["items"]
    assert "+569 •••• 5678" in log[0]["valor_nuevo"] and "12345678" not in log[0]["valor_nuevo"]


def test_resumen_bitacora_y_permisos(client, auth):
    pid, _ = _escenario()
    _evento(client, auth("soporte"), pid, tipo="caida")
    h = auth("analista")  # operación en lectura
    r = client.get(f"{API}/whatsapp/resumen", headers=h).json()
    assert r["modo"] == "simulado" and r["planes_con_whatsapp"] == ["Platino", "Proveedor"]
    assert r["ultimas_24h"]["enviado"] == 1 and r["familiares_habilitados"] == 1
    assert client.get(f"{API}/whatsapp/mensajes", headers=h, params={"q": "humberto"}).json()["total"] == 1
    assert _evento(client, h, pid, tipo="caida").status_code == 403  # analista no puede simular eventos
    assert client.get(f"{API}/whatsapp/resumen", headers=auth("editor")).status_code == 403


def test_integracion_plataforma_con_api_key(client, monkeypatch):
    pid, _ = _escenario()
    url = f"{API}/integracion/eventos-salud"
    assert client.post(url, json={"id_paciente": pid, "tipo": "sos"}).status_code == 503  # sin clave configurada
    monkeypatch.setattr(get_settings(), "plataforma_api_key", "clave-larga")
    assert client.post(url, json={"id_paciente": pid, "tipo": "sos"}, headers={"X-API-Key": "otra"}).status_code == 401
    r = client.post(url, json={"id_paciente": pid, "tipo": "sos"}, headers={"X-API-Key": "clave-larga"})
    assert r.status_code == 201 and r.json()["avisos"][0]["estado"] == "pendiente"
    assert client.post(url, json={"id_paciente": pid, "tipo": "vital"},
                       headers={"X-API-Key": "clave-larga"}).status_code == 422  # falta signo y valor


def test_opciones_para_simular(client, auth):
    pid, _ = _escenario()
    r = client.get(f"{API}/whatsapp/opciones", headers=auth("analista")).json()
    p = next(x for x in r["pacientes"] if x["id_paciente"] == pid)
    assert p["plan"] == "Platino" and p["con_whatsapp"] and p["familiares_habilitados"] == 1
    sat = next(s for s in r["signos"] if s["signo_vital"] == "saturacion_o2")
    assert sat["nombre"] == "Saturación de oxígeno" and sat["verde_min"] == 95 and sat["unidad"] == "%"


# ---------------------------------------------------------------- conexión real: diagnóstico y prueba
def _meta(monkeypatch, respuestas):
    """Activa el modo meta con un urlopen falso que responde según la ruta pedida."""
    st = get_settings()
    for k, v in {"whatsapp_modo": "meta", "whatsapp_token": "tok", "whatsapp_phone_number_id": "123",
                 "whatsapp_waba_id": "999", "whatsapp_app_secret": "s", "whatsapp_verify_token": "v"}.items():
        monkeypatch.setattr(st, k, v)
    llamadas = []

    class Resp:
        def __init__(self, body): self.body = body
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return json.dumps(self.body).encode()

    def fake(req, timeout):
        llamadas.append((req.get_method(), req.full_url, json.loads(req.data) if req.data else None))
        for clave, body in respuestas.items():
            if clave in req.full_url:
                if isinstance(body, Exception):
                    raise body
                return Resp(body)
        raise AssertionError(req.full_url)
    monkeypatch.setattr(wa.urllib.request, "urlopen", fake)
    return llamadas


def test_diagnostico_meta(client, auth, monkeypatch):
    _meta(monkeypatch, {"123?fields": {"display_phone_number": "+1 555-0100", "verified_name": "Test Number",
                                       "quality_rating": "GREEN"},
                        "999/message_templates": {"data": [{"name": "alerta_salud_familiar", "language": "es",
                                                            "status": "PENDING"}]}})
    r = client.get(f"{API}/whatsapp/diagnostico", headers=auth("admin")).json()
    assert r["numero"]["telefono"] == "+1 555-0100" and r["plantilla_estado"] == "PENDING" and r["errores"] == []
    assert client.get(f"{API}/whatsapp/diagnostico", headers=auth("analista")).status_code == 403


def test_diagnostico_token_vencido_explica_el_error(client, auth, monkeypatch):
    import io
    import urllib.error
    vencido = urllib.error.HTTPError("u", 401, "Unauthorized", {}, io.BytesIO(
        b'{"error":{"message":"Error validating access token: Session has expired","code":190}}'))
    _meta(monkeypatch, {"123?fields": vencido, "message_templates": {"data": []}})
    r = client.get(f"{API}/whatsapp/diagnostico", headers=auth("admin")).json()
    assert "token permanente" in r["errores"][0] and r["plantilla_estado"] == "NO EXISTE"


def test_prueba_con_hello_world_mientras_se_aprueba_la_plantilla(client, auth, monkeypatch):
    _, uid = _escenario()
    llamadas = _meta(monkeypatch, {"123/messages": {"messages": [{"id": "wamid.HW1"}]}})
    monkeypatch.setattr(get_settings(), "whatsapp_plantilla", "hello_world")
    r = client.post(f"{API}/whatsapp/prueba", headers=auth("soporte"), json={"id_usuario": uid})
    assert r.status_code == 201 and r.json()["estado"] == "enviado" and r.json()["tipo_mensaje"] == "prueba"
    cuerpo = llamadas[0][2]
    assert cuerpo["template"] == {"name": "hello_world", "language": {"code": "en_US"}}  # sin variables


def test_prueba_fallida_muestra_ayuda_y_no_queda_pendiente(client, auth, monkeypatch):
    import io
    import urllib.error
    _, uid = _escenario()
    no_permitido = urllib.error.HTTPError("u", 400, "Bad Request", {}, io.BytesIO(
        b'{"error":{"message":"Recipient phone number not in allowed list","code":131030}}'))
    _meta(monkeypatch, {"123/messages": no_permitido})
    r = client.post(f"{API}/whatsapp/prueba", headers=auth("soporte"), json={"id_usuario": uid}).json()
    assert r["estado"] == "fallido" and "131030" in r["motivo"] and "destinatarios permitidos" in r["motivo"]


def test_prueba_exige_consentimiento(client, auth):
    _, uid = _escenario(consentimiento=False)
    assert client.post(f"{API}/whatsapp/prueba", headers=auth("soporte"), json={"id_usuario": uid}).status_code == 409
