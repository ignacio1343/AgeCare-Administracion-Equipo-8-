import pytest

from .conftest import API


def nuevo(client, h, **extra):
    data = {"asunto": "Wearable no sincroniza", "descripcion": "Desde ayer", "email_usuario": "ana@example.com",
            "codigo_categoria": "wearable"} | extra
    return client.post(f"{API}/soporte/tickets", headers=h, json=data)


def test_registrar_ticket_enlazado_y_sin_enlazar(client, auth):
    h = auth("soporte")
    r = nuevo(client, h)
    assert r.status_code == 201
    t = r.json()
    assert t["estado"] == "abierto" and t["numero"] > 1000 and t["solicitante"]["id_usuario"] is not None
    r = nuevo(client, h, email_usuario="desconocido@example.com")
    assert r.status_code == 404 and r.json()["error"]["code"] == "USER_NOT_FOUND"
    r = nuevo(client, h, email_usuario="desconocido@example.com", confirmar_sin_enlace=True, nombre_solicitante="Luis")
    assert r.status_code == 201 and r.json()["solicitante"]["nombre"] == "Luis"


def test_permisos_por_rol(client, auth):
    t = nuevo(client, auth("soporte")).json()
    ha = auth("analista")
    assert client.get(f"{API}/soporte/tickets", headers=ha).status_code == 200  # lectura
    assert nuevo(client, ha).status_code == 403  # sin escritura
    assert client.patch(f"{API}/soporte/tickets/{t['id_ticket']}", headers=ha, json={"prioridad": "alta"}).status_code == 403
    assert client.get(f"{API}/soporte/tickets", headers=auth("editor")).status_code == 403  # sin acceso


def test_transiciones_asignacion_y_encuesta(client, auth):
    h = auth("soporte")
    t = nuevo(client, h).json()
    url = f"{API}/soporte/tickets/{t['id_ticket']}"
    r = client.patch(url, headers=h, json={"estado": "cerrado"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "INVALID_TRANSITION"
    r = client.patch(url, headers=h, json={"estado": "en_curso"})
    assert r.json()["asignado"]["nombre"] == "Soporte Prueba"  # quien lo toma queda asignado
    r = client.patch(url, headers=h, json={"estado": "resuelto"})
    assert r.json()["fecha_resolucion"]
    det = client.get(url, headers=h).json()
    assert det["encuesta"] is not None and "cerrado" in det["transiciones_permitidas"]
    assert client.patch(url, headers=h, json={"estado": "cerrado"}).json()["estado"] == "cerrado"
    r = client.post(f"{url}/respuestas", headers=h, json={"cuerpo": "hola"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "TICKET_CLOSED"


def test_primera_respuesta_ignora_notas_internas(client, auth):
    h = auth("soporte")
    t = nuevo(client, h).json()
    url = f"{API}/soporte/tickets/{t['id_ticket']}"
    client.post(f"{url}/respuestas", headers=h, json={"cuerpo": "nota", "es_interna": True})
    assert client.get(url, headers=h).json()["fecha_primera_respuesta"] is None
    client.post(f"{url}/respuestas", headers=h, json={"cuerpo": "Hola Ana, revisa el Bluetooth"})
    assert client.get(url, headers=h).json()["fecha_primera_respuesta"] is not None
    conv = client.get(f"{url}/respuestas", headers=h).json()
    assert [r["es_interna"] for r in conv] == [True, False]


def test_asignar_a_quien_no_puede_atender(client, auth):
    h = auth("admin")
    t = nuevo(client, h).json()
    editores = client.get(f"{API}/staff", headers=h, params={"codigo_rol": "editor"}).json()["items"]
    r = client.patch(f"{API}/soporte/tickets/{t['id_ticket']}", headers=h, json={"id_staff_asignado": editores[0]["id_staff"]})
    assert r.status_code == 404 and r.json()["error"]["code"] == "ASSIGNEE_NOT_FOUND"
    r = client.patch(f"{API}/soporte/tickets/{t['id_ticket']}", headers=h, json={"id_staff_asignado": None})
    assert r.status_code == 200 and r.json()["asignado"] is None


@pytest.mark.parametrize("q", ["Wearable", "ana@example.com", "#1001", "1001"])
def test_busqueda_en_cola(client, auth, q):
    h = auth("soporte")
    nuevo(client, h)
    r = client.get(f"{API}/soporte/tickets", headers=h, params={"q": q})
    assert r.json()["total"] == 1


def test_detalle_por_numero_y_indicadores(client, auth):
    h = auth("soporte")
    t = nuevo(client, h).json()
    assert client.get(f"{API}/soporte/tickets/%23{t['numero']}", headers=h).json()["id_ticket"] == t["id_ticket"]
    ind = client.get(f"{API}/soporte/indicadores", headers=h).json()
    assert ind["abiertos"] == 1 and ind["sin_asignar"] == 1
    assert ind["por_categoria_30d"][0]["codigo"] == "wearable"


def test_escrituras_quedan_en_auditoria(client, auth):
    h = auth("soporte")
    t = nuevo(client, h).json()
    client.patch(f"{API}/soporte/tickets/{t['id_ticket']}", headers=h, json={"prioridad": "critica"})
    log = client.get(f"{API}/auditoria", headers=auth("admin"), params={"tipo_entidad": "ticket"}).json()["items"]
    assert [x["accion"] for x in log] == ["ticket.actualizar", "ticket.crear"]
    assert log[0]["actor_nombre"] == "Soporte Prueba"
