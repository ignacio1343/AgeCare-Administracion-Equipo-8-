"""Carga catálogos y datos demo.  Uso:  python -m scripts.seed  [--reset]

--reset borra y recrea todas las tablas (solo para desarrollo).
"""
import random
import sys
from datetime import timedelta

from sqlalchemy import func, select

from app.catalogos import cargar_catalogos
from app.db import Base, SessionLocal, engine, utcnow
from app.models import (EncuestaSatisfaccion, MembresiaCirculo, MiembroStaff, Paciente, RespuestaTicket, Ticket,
                        UsuarioApp, UsuarioPerfil)
from app.security import hash_password

STAFF = [
    ("Max K.", "admin@wellq.co.uk", "admin", "Admin123!"),
    ("Sofía Soporte", "soporte@wellq.co.uk", "soporte", "Soporte123!"),
    ("Tomás Rivas", "tomas.rivas@wellq.co.uk", "soporte", "Soporte123!"),
    ("Ana Analista", "analista@wellq.co.uk", "analista", "Analista123!"),
    ("Elena Editora", "editora@wellq.co.uk", "editor", "Editora123!"),
    ("Mario Moderador", "moderador@wellq.co.uk", "moderador", "Moderador123!"),
]

NOMBRES = ["Ana Pérez", "Rosa Díaz", "Carlos Muñoz", "Lucía Rojas", "Pedro Soto", "Camila Fuentes", "Jorge Vidal",
           "Valentina Castro", "Diego Herrera", "Francisca Morales", "Andrés Silva", "Isidora Núñez", "Matías Reyes",
           "Javiera Torres", "Felipe Araya", "Daniela Contreras", "Sebastián Pino", "Catalina Vega", "Ricardo Lagos M.",
           "Dra. Paula Méndez"]
PACIENTES = ["Hilda Pérez", "Raúl Díaz", "Olga Muñoz", "Ernesto Rojas", "Marta Soto", "Luis Fuentes", "Teresa Vidal",
             "Humberto Castro"]

ASUNTOS = {
    "wearable": ["Wearable no sincroniza desde ayer", "La pulsera no muestra la frecuencia cardíaca",
                 "Batería del wearable se agota en horas", "No puedo vincular el reloj nuevo"],
    "alertas_push": ["No llegan las alertas de medicamentos", "Me llegó una alerta de caída falsa",
                     "Las notificaciones llegan con mucho retraso", "El botón SOS no notificó a la familia"],
    "acceso_cuenta": ["No puedo iniciar sesión", "No me llega el correo para cambiar contraseña",
                      "La invitación al círculo de cuidado expiró", "Quiero cambiar el correo de mi cuenta"],
    "pagos_planes": ["Cambio de plan Dorado → Platino", "Me cobraron dos veces este mes", "¿Cómo cancelo mi plan?",
                     "No se aplicó el descuento del plan Proveedor"],
    "medicamentos": ["Error al digitalizar receta (OCR)", "El médico no puede editar el plan",
                     "La dosis aparece duplicada en el calendario"],
    "otros": ["Audio del Director Musical no sube", "Sugerencia: modo oscuro", "La app se cierra al abrir fotos"],
}
RESPUESTAS_STAFF = ["Hola, gracias por escribirnos. Estamos revisando tu caso.",
                    "¿Puedes confirmar el modelo del dispositivo y la versión de la app?",
                    "Ya aplicamos una corrección. ¿Puedes probar nuevamente?",
                    "Te dejamos los pasos: cerrar sesión, actualizar la app y volver a ingresar."]
RESPUESTAS_USUARIO = ["Gracias, quedo atenta.", "Es un iPhone 13 con la última versión.", "Ya funciona, muchas gracias.",
                      "Sigue igual, lo probé dos veces."]


def run(reset: bool = False) -> None:
    if reset:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    rnd = random.Random(42)
    now = utcnow()
    with SessionLocal() as db:
        cargar_catalogos(db)

        staff = {}
        for nombre, email, rol, pwd in STAFF:
            s = db.scalar(select(MiembroStaff).where(MiembroStaff.email == email))
            if s is None:
                s = MiembroStaff(nombre_completo=nombre, email=email, codigo_rol=rol, estado="activo",
                                 password_hash=hash_password(pwd), mfa_requerido=(rol == "admin"),
                                 fecha_activacion=now - timedelta(days=60), fecha_creacion=now - timedelta(days=60))
                db.add(s)
            staff[email] = s
        db.flush()

        if db.scalar(select(func.count()).select_from(Ticket)):
            db.commit()
            print("Catálogos y staff verificados. Ya existen tickets: no se regeneran los datos del Avance 2.")
            _modulos(db)
            return

        pacientes = [Paciente(nombre=n, fecha_alta=now - timedelta(days=rnd.randint(60, 300))) for n in PACIENTES]
        db.add_all(pacientes)
        usuarios = []
        for i, n in enumerate(NOMBRES):
            email = n.lower().replace("dra. ", "").replace(" ", ".").replace(".m.", "").translate(
                str.maketrans("áéíóúñ", "aeioun")).rstrip(".") + "@example.com"
            u = UsuarioApp(nombre=n, email=email, fecha_registro=now - timedelta(days=rnd.randint(20, 300)),
                           ultimo_acceso=now - timedelta(hours=rnd.randint(1, 200)))
            db.add(u)
            usuarios.append(u)
        db.flush()
        for i, u in enumerate(usuarios):
            perfil = "medico" if u.nombre.startswith("Dra.") else ("cuidadora" if i % 4 == 1 else "familiar")
            db.add(UsuarioPerfil(id_usuario=u.id_usuario, codigo_perfil=perfil))
            p = pacientes[i % len(pacientes)]
            db.add(MembresiaCirculo(id_usuario=u.id_usuario, id_paciente=p.id_paciente, rol_en_circulo=perfil,
                                    estado="activo" if i % 7 else "invitado", fecha_invitacion=u.fecha_registro,
                                    fecha_aceptacion=u.fecha_registro + timedelta(days=1) if i % 7 else None))

        db.flush()
        for u in usuarios:
            db.refresh(u)
        agentes = [staff["soporte@wellq.co.uk"], staff["tomas.rivas@wellq.co.uk"], staff["admin@wellq.co.uk"]]
        cats = list(ASUNTOS)
        for k in range(46):
            cat = rnd.choices(cats, weights=[24, 14, 32, 12, 9, 9])[0]
            u = rnd.choice(usuarios)
            creado = now - timedelta(days=rnd.uniform(0, 44), hours=rnd.uniform(0, 12))
            edad = (now - creado).days
            estado = ("abierto" if edad < 6 and rnd.random() < .55 else
                      rnd.choices(["en_curso", "esperando_usuario", "resuelto", "cerrado"], weights=[3, 2, 6, 4])[0]
                      if edad > 1 else rnd.choice(["abierto", "en_curso"]))
            if estado == "resuelto" and edad > 9:
                estado = "cerrado"  # el job de cierre automático ya los habría cerrado
            if estado == "cerrado" and edad < 8:
                estado = "resuelto"
            t = Ticket(asunto=rnd.choice(ASUNTOS[cat]), codigo_categoria=cat, id_usuario=u.id_usuario,
                       nombre_solicitante=u.nombre, email_solicitante=u.email,
                       id_paciente=u.membresias[0].id_paciente if u.membresias else None,
                       descripcion=f"{u.nombre.split()[0]} reporta el problema desde la app. Detalle entregado por el usuario.",
                       prioridad=rnd.choices(["baja", "media", "alta", "critica"], weights=[2, 5, 3, 1])[0],
                       canal=rnd.choices(["app", "correo", "telefono"], weights=[6, 2, 1])[0], estado=estado,
                       fecha_creacion=creado, fecha_actualizacion=creado)
            db.add(t)
            db.flush()
            t.numero = 1000 + t.id_ticket
            t.fecha_actualizacion = creado
            if estado != "abierto":
                ag = rnd.choice(agentes)
                t.id_staff_asignado = ag.id_staff
                primera = creado + timedelta(hours=rnd.uniform(0.3, 7))
                t.fecha_primera_respuesta = min(primera, now)
                db.add(RespuestaTicket(id_ticket=t.id_ticket, id_staff_autor=ag.id_staff, tipo_autor="staff",
                                       cuerpo=rnd.choice(RESPUESTAS_STAFF), fecha=t.fecha_primera_respuesta))
                if rnd.random() < .5:
                    db.add(RespuestaTicket(id_ticket=t.id_ticket, id_staff_autor=ag.id_staff, tipo_autor="staff",
                                           es_interna=True, cuerpo="Nota interna: revisar logs de sincronización.",
                                           fecha=t.fecha_primera_respuesta + timedelta(minutes=10)))
                db.add(RespuestaTicket(id_ticket=t.id_ticket, tipo_autor="usuario", cuerpo=rnd.choice(RESPUESTAS_USUARIO),
                                       fecha=t.fecha_primera_respuesta + timedelta(hours=1)))
                t.fecha_actualizacion = t.fecha_primera_respuesta + timedelta(hours=1)
            if estado in ("resuelto", "cerrado"):
                t.fecha_resolucion = min(creado + timedelta(hours=rnd.uniform(6, 60)), now)
                enc = EncuestaSatisfaccion(id_ticket=t.id_ticket, fecha_envio=t.fecha_resolucion)
                if rnd.random() < .7:
                    enc.puntaje = rnd.choices([5, 4, 3, 2], weights=[6, 3, 1, 1])[0]
                    enc.fecha_respuesta = t.fecha_resolucion + timedelta(hours=3)
                    enc.comentario = "Muy buena atención." if enc.puntaje >= 4 else None
                db.add(enc)
                if estado == "cerrado":
                    t.fecha_cierre = t.fecha_resolucion + timedelta(days=7)
        db.commit()
        print(f"Datos demo cargados: {len(STAFF)} staff, {len(usuarios)} usuarios, {len(pacientes)} pacientes, 46 tickets.")
        _modulos(db)


def _modulos(db) -> None:
    try:
        from scripts.seed_modulos import cargar
    except ImportError:  # los datos de los módulos de negocio se agregan con su paquete
        print("Módulos: datos de demostración pendientes (scripts/seed_modulos.py aún no está en el repositorio).")
        return
    hechos = cargar(db)
    print("Módulos: " + (", ".join(hechos) if hechos else "sin cambios (ya tenían datos)."))


if __name__ == "__main__":
    run(reset="--reset" in sys.argv)
