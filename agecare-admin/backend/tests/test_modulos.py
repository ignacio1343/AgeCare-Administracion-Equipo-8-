"""Reglas de negocio de los módulos de los sprints 3 a 5."""
import hashlib
import hmac
import json
from datetime import date, timedelta

from app.db import SessionLocal, utcnow
from app.models import (ElementoModeracion, MembresiaCirculo, Paciente, PerfilCuidadora, TransaccionPago, UsuarioApp,
                        UsuarioPerfil)

from .conftest import API


def _datos():
    with SessionLocal() as db:
        u = db.query(UsuarioApp).filter_by(email="ana@example.com").one()
        p = Paciente(nombre="Hilda Pérez")
        db.add(p)
        db.flush()
        db.add(UsuarioPerfil(id_usuario=u.id_usuario, codigo_perfil="cuidadora"))
        db.add(MembresiaCirculo(id_usuario=u.id_usuario, id_paciente=p.id_paciente, rol_en_circulo="familiar", estado="invitado"))
        db.add(PerfilCuidadora(id_usuario=u.id_usuario, zona="Ñuñoa", certificaciones_verificadas=0))
        db.add(ElementoModeracion(id_usuario_autor=u.id_usuario, tipo_elemento="resena", contenido_reportado="texto"))
        db.commit()
        return u.id_usuario, p.id_paciente


# ---------------------------------------------------------------- usuarios de la app
def test_usuarios_buscar_desactivar_e_invitar(client, auth):
    uid, pid = _datos()
    h = auth("soporte")
    assert client.get(f"{API}/usuarios", headers=h, params={"q": "hilda"}).json()["total"] == 1  # busca por paciente
    r = client.patch(f"{API}/usuarios/{uid}/estado", headers=h, json={"estado_cuenta": "desactivada", "motivo": "x"})
    assert r.status_code == 422  # motivo obligatorio
    r = client.patch(f"{API}/usuarios/{uid}/estado", headers=h, json={"estado_cuenta": "desactivada", "motivo": "Solicitud del titular"})
    assert r.json()["estado_cuenta"] == "desactivada"
    assert client.post(f"{API}/usuarios/{uid}/membresias/{pid}/invitacion", headers=h).status_code == 200
    assert client.get(f"{API}/usuarios", headers=auth("analista")).status_code == 403


# ---------------------------------------------------------------- estado operativo
def test_monitor_abre_incidente_tras_tres_fallos(client, auth):
    h = auth("soporte")
    for i in range(3):
        nuevos = client.post(f"{API}/operacion/monitor/ciclo", headers=h, params={"simular_falla": "storage"}).json()
    assert len(nuevos) == 1 and nuevos[0]["creado_automaticamente"]
    estado = client.get(f"{API}/operacion/estado", headers=h).json()
    assert estado["estado_general"] == "caido" and estado["incidentes_abiertos"] == 1
    # el proceso crítico que usa ese componente también cae
    assert next(p for p in estado["procesos"] if p["codigo"] == "musica")["estado"] == "caido"
    # un 4.º fallo no duplica el incidente
    assert client.post(f"{API}/operacion/monitor/ciclo", headers=h, params={"simular_falla": "storage"}).json() == []


def test_ciclo_de_vida_de_incidente(client, auth):
    h = auth("soporte")
    i = client.post(f"{API}/operacion/incidentes", headers=h, json={"titulo": "Push con retraso", "descripcion": "Cola saturada",
                                                                     "severidad": "degradado", "codigo_componente": "push"}).json()
    url = f"{API}/operacion/incidentes/{i['id_incidente']}"
    assert client.patch(url, headers=h, json={"estado": "resuelto"}).json()["error"]["code"] == "RESOLUTION_REQUIRED"
    assert client.patch(url, headers=h, json={"estado": "completado"}).json()["error"]["code"] == "INVALID_TRANSITION"
    r = client.patch(url, headers=h, json={"estado": "resuelto", "resolucion": "Se amplió la capacidad"})
    assert r.json()["estado"] == "resuelto" and r.json()["fecha_resolucion"]
    assert client.patch(url, headers=h, json={"descripcion": "otra cosa"}).status_code == 409
    m = client.post(f"{API}/operacion/incidentes", headers=h, json={"titulo": "Mantención BD", "descripcion": "Ventana nocturna",
                                                                     "severidad": "degradado", "es_mantenimiento": True}).json()
    assert m["transiciones_permitidas"] == ["completado"]
    assert client.get(f"{API}/operacion/estado", headers=auth("editor")).status_code == 403


# ---------------------------------------------------------------- contenidos, productos, cuidadoras
def test_contenido_publicar_programar_y_eliminar(client, auth):
    h = auth("editor")
    c = client.post(f"{API}/contenidos", headers=h, json={"tipo": "chiste", "titulo": "El reloj", "cuerpo": "¿Por qué el reloj fue al médico?"}).json()
    assert c["estado"] == "borrador"
    futuro = (utcnow() + timedelta(days=2)).isoformat()
    r = client.post(f"{API}/contenidos/{c['id_contenido']}/publicar", headers=h, json={"fecha_programada": futuro})
    assert r.json()["estado"] == "programado"
    r = client.post(f"{API}/contenidos/{c['id_contenido']}/publicar", headers=h, json={})
    assert r.json()["estado"] == "publicado"
    assert client.delete(f"{API}/contenidos/{c['id_contenido']}", headers=h).json()["error"]["code"] == "PUBLISHED"
    client.post(f"{API}/contenidos/{c['id_contenido']}/archivar", headers=h)
    assert client.delete(f"{API}/contenidos/{c['id_contenido']}", headers=h).status_code == 204
    assert client.get(f"{API}/contenidos", headers=h).json()["total"] == 0
    assert client.get(f"{API}/contenidos", headers=auth("soporte")).status_code == 403


def test_producto_exige_https(client, auth):
    h = auth("editor")
    base = {"nombre": "Bastón", "categoria": "movilidad", "proveedor": "OrtoSalud"}
    assert client.post(f"{API}/productos", headers=h, json=base | {"url_externa": "http://x.cl/p"}).status_code == 422
    assert client.post(f"{API}/productos", headers=h, json=base | {"url_externa": "https://x.cl/p"}).status_code == 201
    assert client.post(f"{API}/productos", headers=auth("moderador"), json=base | {"url_externa": "https://x.cl/p"}).status_code == 403


def test_revision_de_cuidadora(client, auth):
    _datos()
    h = auth("editor")
    pid = client.get(f"{API}/cuidadoras", headers=h).json()["items"][0]["id_perfil"]
    url = f"{API}/cuidadoras/{pid}/revision"
    assert client.post(url, headers=h, json={"decision": "aprobado"}).json()["error"]["code"] == "CERTIFICATION_REQUIRED"
    assert client.post(url, headers=h, json={"decision": "suspendido"}).json()["error"]["code"] == "REASON_REQUIRED"
    r = client.post(url, headers=h, json={"decision": "suspendido", "motivo": "Documentación incompleta"})
    assert r.json()["estado_publicacion"] == "suspendido" and r.json()["revisor"] == "Editor Prueba"


# ---------------------------------------------------------------- moderación
def test_moderacion_reglas(client, auth):
    _datos()
    h = auth("moderador")
    eid = client.get(f"{API}/moderacion/cola", headers=h).json()["items"][0]["id_elemento"]
    url = f"{API}/moderacion/{eid}/decision"
    assert client.post(url, headers=h, json={"decision": "rechazado"}).json()["error"]["code"] == "REASON_REQUIRED"
    assert client.post(url, headers=h, json={"decision": "rechazado", "motivo_rechazo": "otro"}).json()["error"]["code"] == "NOTE_REQUIRED"
    r = client.post(url, headers=h, json={"decision": "rechazado", "motivo_rechazo": "ofensivo"})
    assert r.json()["estado"] == "rechazado" and r.json()["autor_rechazos_90d"] == 1
    assert client.post(url, headers=h, json={"decision": "aprobado"}).json()["error"]["code"] == "ALREADY_MODERATED"


# ---------------------------------------------------------------- planes, suscripciones y pagos
def _firma(body: bytes) -> str:
    return hmac.new(b"secreto-webhook-demo", body, hashlib.sha256).hexdigest()


def test_flujo_comercial_completo(client, auth):
    h = auth("admin")
    assert client.put(f"{API}/comercial/planes/gratuito", headers=h, json={"precio": 500}).json()["error"]["code"] == "FREE_PLAN"
    r = client.post(f"{API}/comercial/cuentas", headers=h, json={"email_titular": "ana@example.com", "tipo_cuenta": "familia",
                                                                  "nombre": "Familia Pérez", "email_facturacion": "ana@example.com",
                                                                  "rut": "11.111.111-2", "codigo_plan": "dorado"})
    assert r.status_code == 422  # RUT inválido
    r = client.post(f"{API}/comercial/cuentas", headers=h, json={"email_titular": "ana@example.com", "tipo_cuenta": "familia",
                                                                  "nombre": "Familia Pérez", "email_facturacion": "ana@example.com",
                                                                  "rut": "11.111.111-1", "codigo_plan": "dorado"})
    assert r.status_code == 201
    sus = r.json()["suscripcion_actual"]
    ext = client.get(f"{API}/comercial/cuentas/{r.json()['id_cuenta']}", headers=h).json()
    with SessionLocal() as db:
        from app.models import Suscripcion
        sid_ext = db.get(Suscripcion, sus["id_suscripcion"]).id_externo_pasarela
    # CU14: la pasarela informa un pago (firma obligatoria, idempotente)
    body = json.dumps({"id_evento": "evt_1", "tipo": "pago.aprobado", "id_suscripcion_externa": sid_ext,
                       "id_transaccion_externa": "tx_1", "monto": 1000}).encode()
    assert client.post(f"{API}/pagos/webhook", content=body, headers={"X-Pasarela-Firma": "mala"}).status_code == 401
    assert client.post(f"{API}/pagos/webhook", content=body, headers={"X-Pasarela-Firma": _firma(body)}).json()["procesado"]
    assert client.post(f"{API}/pagos/webhook", content=body, headers={"X-Pasarela-Firma": _firma(body)}).json()["duplicado"]
    tx = client.get(f"{API}/comercial/transacciones", headers=h).json()["items"][0]
    assert tx["estado"] == "aprobada" and tx["reembolsable"] == 1000
    # CU15: reembolso parcial y tope
    url = f"{API}/comercial/transacciones/{tx['id_transaccion']}/reembolsos"
    assert client.post(url, headers=h, json={"monto": 1500, "motivo": "Cobro duplicado"}).json()["error"]["code"] == "AMOUNT_EXCEEDED"
    r = client.post(url, headers=h, json={"monto": 400, "motivo": "Cobro duplicado"})
    assert r.status_code == 201 and r.json()["reembolsable"] == 600
    # pago rechazado -> en mora
    body = json.dumps({"id_evento": "evt_2", "tipo": "pago.rechazado", "id_suscripcion_externa": sid_ext,
                       "id_transaccion_externa": "tx_2", "monto": 1000, "codigo_error": "fondos_insuficientes"}).encode()
    client.post(f"{API}/pagos/webhook", content=body, headers={"X-Pasarela-Firma": _firma(body)})
    assert client.get(f"{API}/comercial/suscripciones", headers=h, params={"estado": "en_mora"}).json()["total"] == 1
    # CU11 / CU12
    sid = sus["id_suscripcion"]
    assert client.patch(f"{API}/comercial/suscripciones/{sid}/plan", headers=h, json={"codigo_plan": "platino"}).json()["plan"] == "Platino"
    r = client.post(f"{API}/comercial/suscripciones/{sid}/cancelar", headers=h, json={"motivo": "Solicitud del cliente"})
    assert r.json()["estado"] == "cancelada"
    assert client.post(f"{API}/comercial/suscripciones/{sid}/cancelar", headers=h, json={"motivo": "otra vez"}).status_code == 409
    assert ext["tipo_cuenta"] == "familia"
    assert client.get(f"{API}/comercial/planes", headers=auth("soporte")).status_code == 403
    assert client.put(f"{API}/comercial/planes/dorado", headers=auth("analista"), json={"precio": 1}).status_code == 403


# ---------------------------------------------------------------- dashboards
def test_metricas_y_consolidacion(client, auth):
    h = auth("analista")
    assert client.get(f"{API}/metricas/comerciales", headers=h, params={"periodo": "30d"}).status_code == 200
    assert client.get(f"{API}/metricas/adopcion", headers=h).json()["filas"][0]["celdas"][0]["adopcion"] is None
    assert client.post(f"{API}/metricas/consolidar", headers=h).status_code == 403  # analista solo lee
    client.post(f"{API}/soporte/tickets", headers=auth("soporte"), json={"asunto": "No sincroniza", "descripcion": "x",
                                                                         "email_usuario": "ana@example.com", "codigo_categoria": "wearable"})
    assert client.post(f"{API}/metricas/consolidar", headers=auth("admin")).status_code == 200
    serie = client.get(f"{API}/metricas/soporte", headers=h).json()
    assert serie["creados"][-1] == 1
    assert client.get(f"{API}/metricas/comerciales", headers=auth("editor")).status_code == 403


# ---------------------------------------------------------------- configuración y legales
def test_parametros_con_bloqueo_optimista(client, auth):
    h = auth("admin")
    p = next(x for x in client.get(f"{API}/configuracion/parametros", headers=h).json() if x["clave"] == "churn_dias_inactividad")
    url = f"{API}/configuracion/parametros/churn_dias_inactividad"
    assert client.put(url, headers=h, json={"valor": "treinta", "version": p["version"], "nota_cambio": "ajuste"}).status_code == 422
    r = client.put(url, headers=h, json={"valor": "45", "version": p["version"], "nota_cambio": "ajuste"})
    assert r.json()["version"] == p["version"] + 1
    r = client.put(url, headers=h, json={"valor": "60", "version": p["version"], "nota_cambio": "otro"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "VERSION_CONFLICT"
    assert client.get(f"{API}/configuracion/parametros", headers=auth("soporte")).status_code == 403


def test_umbrales(client, auth):
    h = auth("admin")
    url = f"{API}/configuracion/umbrales/frecuencia_cardiaca/verde"
    assert client.put(url, headers=h, json={"valor_minimo": 110, "valor_maximo": 90}).json()["error"]["code"] == "INVALID_RANGE"
    assert client.put(url, headers=h, json={"valor_minimo": 55, "valor_maximo": 100}).json()["valor_minimo"] == 55


def test_versiones_legales(client, auth):
    h = auth("admin")
    texto = "Términos de uso de AgeCare. " * 6
    hoy = date.today().isoformat()
    v1 = client.post(f"{API}/legales/versiones", headers=h, json={"tipo_documento": "terminos", "contenido": texto,
                                                                  "registro_cambios": "Inicial", "fecha_vigencia": hoy}).json()
    assert v1["version"] == "1.0" and v1["estado"] == "borrador"
    assert client.post(f"{API}/legales/versiones", headers=h, json={"tipo_documento": "terminos", "contenido": texto,
                                                                    "registro_cambios": "Otro cambio", "fecha_vigencia": hoy}).status_code == 409
    client.post(f"{API}/legales/versiones/{v1['id_version']}/publicar", headers=h)
    assert client.patch(f"{API}/legales/versiones/{v1['id_version']}", headers=h, json={"registro_cambios": "cambio"}).status_code == 409
    v2 = client.post(f"{API}/legales/versiones", headers=h, json={"tipo_documento": "terminos", "contenido": texto + " Nuevo.",
                                                                  "registro_cambios": "Nueva cláusula", "fecha_vigencia": hoy,
                                                                  "cambio_mayor": True}).json()
    assert v2["version"] == "2.0" and v2["requiere_reaceptacion"]
    client.post(f"{API}/legales/versiones/{v2['id_version']}/publicar", headers=h)
    estados = {v["version"]: v["estado"] for v in client.get(f"{API}/legales/versiones", headers=h).json()}
    assert estados == {"2.0": "publicada", "1.0": "reemplazada"}
    assert client.get(f"{API}/legales/publico/terminos").json()["version"] == "2.0"  # público, sin token


def test_health_y_health_db(client):
    r = client.get(f"{API}/health")
    assert r.status_code == 200 and r.json()["version"] == "0.5.1"
    r = client.get(f"{API}/health/db")
    assert r.status_code == 200 and r.json()["db_ms"] >= 0


def test_registro_de_acceso_una_linea_sin_query(client, caplog):
    import logging
    with caplog.at_level(logging.INFO, logger="acceso"):
        client.get(f"{API}/auth/me?token=secreto")
    linea = [r.getMessage() for r in caplog.records if r.name == "acceso"][-1]
    assert linea.startswith("GET /api/v1/auth/me 401 ") and "rid=" in linea and "secreto" not in linea
