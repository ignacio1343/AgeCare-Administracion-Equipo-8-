"""Datos demo de los módulos de los sprints 3 a 5. Cada bloque solo se carga si su tabla está vacía,
así también sirve para actualizar una base creada en el Avance 2."""
import math
import random
from datetime import date, timedelta

from sqlalchemy import func, select

from app.db import utcnow
from app.metricas_job import consolidar_soporte
from app.models import (ActividadPerfil, AdopcionFuncionalidad, Alerta, Componente, Contenido, CuentaCliente,
                        ElementoModeracion, Incidente, MensajeWhatsapp, MetricaDiaria, MiembroStaff, Paciente,
                        PerfilCuidadora, Plan, Producto, SnapshotEmbudo, SnapshotPlan, Suscripcion, TransaccionPago,
                        UsuarioApp, VerificacionSalud, VersionLegal)
from app.monitor import BASE_LATENCIA


def _vacia(db, modelo) -> bool:
    return not db.scalar(select(func.count()).select_from(modelo))


def cargar(db, rnd: random.Random | None = None) -> list[str]:
    rnd = rnd or random.Random(7)
    now = utcnow()
    hechos = []
    usuarios = db.scalars(select(UsuarioApp).order_by(UsuarioApp.id_usuario)).all()
    pacientes = db.scalars(select(Paciente).order_by(Paciente.id_paciente)).all()
    staff = {s.email: s for s in db.scalars(select(MiembroStaff))}
    admin = staff.get("admin@wellq.co.uk")
    editora = staff.get("editora@wellq.co.uk")
    moderador = staff.get("moderador@wellq.co.uk")
    soporte = staff.get("soporte@wellq.co.uk")

    # ---------------------------------------------------------------- estado operativo: 30 días de verificaciones horarias
    if _vacia(db, VerificacionSalud):
        comps = db.scalars(select(Componente)).all()
        for c in comps:
            tasa_falla = {"ai_assistant": .022, "push": .004, "music_sync": .008}.get(c.codigo_componente, .0004)
            buenos = total = 0
            lats = []
            for h in range(30 * 24, 0, -1):
                ok = rnd.random() > tasa_falla
                lat = int(rnd.lognormvariate(0, .35) * BASE_LATENCIA.get(c.codigo_componente, 150)) if ok else None
                db.add(VerificacionSalud(codigo_componente=c.codigo_componente, fecha_hora=now - timedelta(hours=h),
                                         exitosa=ok, latencia_ms=lat, detalle=None if ok else "Timeout"))
                total += 1
                buenos += ok
                if lat:
                    lats.append(lat)
            ult = sorted(lats[-60:])
            c.uptime_30d = round(buenos / total, 5)
            c.latencia_p50_ms, c.latencia_p95_ms = ult[len(ult) // 2], ult[int(.95 * (len(ult) - 1))]
            c.estado_actual = "degradado" if c.latencia_p95_ms > c.umbral_p95_ms else "operativo"
            c.estado_desde = now - timedelta(hours=rnd.randint(2, 200))
        hechos.append("verificaciones de salud (30 días)")

    if _vacia(db, Incidente):
        db.add_all([
            Incidente(codigo_componente="ai_assistant", titulo="Latencia elevada en el Asistente IA", severidad="degradado",
                      estado="en_observacion", descripcion="p95 de generación sobre 4 s por saturación del proveedor LLM.",
                      fecha_inicio=now - timedelta(days=2, hours=3), id_staff_responsable=soporte.id_staff if soporte else None),
            Incidente(codigo_componente="push", titulo="Notificaciones push retrasadas 23 min", severidad="degradado",
                      estado="resuelto", descripcion="Cola de Notification Hubs saturada tras un pico de alertas.",
                      resolucion="Se amplió el plan y se agregó una alarma de profundidad de cola.",
                      fecha_inicio=now - timedelta(days=9), fecha_resolucion=now - timedelta(days=9, hours=-2),
                      id_staff_responsable=admin.id_staff if admin else None),
            Incidente(codigo_componente="database", titulo="Mantenimiento programado de base de datos", severidad="degradado",
                      estado="completado", es_mantenimiento=True,
                      descripcion="Actualización menor de PostgreSQL Flexible con réplica y failover.",
                      resolucion="Completado sin corte de servicio.", fecha_inicio=now - timedelta(days=21),
                      fecha_resolucion=now - timedelta(days=21, hours=-1)),
        ])
        hechos.append("incidentes")

    if _vacia(db, Alerta) and pacientes:
        tipos = [("medicamento", "media", .55), ("vital", "alta", .3), ("caida", "critica", .1), ("sos", "critica", .05)]
        for _ in range(260):
            t, sev, _p = rnd.choices(tipos, weights=[x[2] for x in tipos])[0]
            emit = now - timedelta(minutes=rnd.uniform(5, 7 * 24 * 60))
            atendida = rnd.random() < (.97 if emit < now - timedelta(hours=2) else .6)
            minutos = rnd.lognormvariate(1.6 if sev == "critica" else 2.6, .6)
            db.add(Alerta(id_paciente=rnd.choice(pacientes).id_paciente, codigo_tipo=t, severidad=sev, fecha_emision=emit,
                          estado="atendida" if atendida else "activa",
                          fecha_atencion=emit + timedelta(minutes=minutos) if atendida else None))
        hechos.append("alertas (7 días)")

    # ---------------------------------------------------------------- contenidos y productos
    if _vacia(db, Contenido):
        chistes = [("¿Qué le dijo el café al azúcar?", "Sin ti mi vida es amarga. Y con leche, un poco más tranquila."),
                   ("El reloj", "¿Por qué el reloj fue al médico? Porque tenía las manecillas atrasadas."),
                   ("La planta", "¿Qué le dijo una planta a otra? ¡Qué gusto verte tan florecida esta mañana!"),
                   ("El pan", "¿Por qué el pan no habla? Porque está en la luna de miel… con la mantequilla.")]
        noticias = [("Coro de adultos mayores gana premio regional", "El coro «Voces de Ñuñoa» obtuvo el primer lugar en el festival regional de música."),
                    ("Comienza la temporada de cerezas", "Los productores de la zona central anuncian una buena temporada y precios estables."),
                    ("Nueva ruta de buses con piso bajo", "La línea 210 incorpora 40 buses de piso bajo para facilitar el acceso."),
                    ("Taller gratuito de memoria en bibliotecas", "Las bibliotecas municipales abren talleres de estimulación cognitiva los martes.")]
        for i, (t, c) in enumerate(chistes):
            db.add(Contenido(tipo="chiste", titulo=t, cuerpo=c, etiquetas="humor", estado="publicado" if i < 3 else "borrador",
                             fecha_publicacion=now - timedelta(days=10 - i) if i < 3 else None, fecha_creacion=now - timedelta(days=12 - i)))
        for i, (t, c) in enumerate(noticias):
            estado = ["publicado", "publicado", "programado", "borrador"][i]
            db.add(Contenido(tipo="noticia", titulo=t, cuerpo=c, etiquetas="comunidad,actualidad", estado=estado,
                             fecha_publicacion=now - timedelta(days=4 - i) if estado == "publicado" else None,
                             fecha_programada=now + timedelta(days=2) if estado == "programado" else None,
                             fecha_creacion=now - timedelta(days=6 - i)))
        hechos.append("contenidos")

    if _vacia(db, Producto):
        prods = [("Bastón ortopédico regulable", "movilidad", "OrtoSalud", 18990), ("Silla de ducha con respaldo", "baño", "BañoSeguro", 34990),
                 ("Pastillero semanal con alarma", "medicamentos", "MediBox", 12490), ("Barra de apoyo para baño", "baño", "BañoSeguro", 15990),
                 ("Andador con ruedas y asiento", "movilidad", "OrtoSalud", 79990), ("Oxímetro de pulso", "monitoreo", "VitalTech", 14990),
                 ("Lupa con luz LED", "visión", "VerBien", 9990), ("Cojín antiescaras", "cuidado", "CuidarMás", 29990)]
        for i, (n, c, p, precio) in enumerate(prods):
            db.add(Producto(nombre=n, categoria=c, proveedor=p, precio_referencial=precio,
                            url_externa=f"https://tienda.ejemplo.cl/p/{i + 1}", estado="publicado" if i < 6 else "borrador"))
        hechos.append("productos")

    if _vacia(db, PerfilCuidadora):
        cuid = [u for u in usuarios if any(p.codigo_perfil == "cuidadora" for p in u.perfiles)]
        zonas = ["Ñuñoa", "Providencia", "Maipú", "La Florida", "Viña del Mar", "Concepción"]
        for i, u in enumerate(cuid):
            estado = ["aprobado", "aprobado", "pendiente", "pendiente", "suspendido"][i % 5]
            db.add(PerfilCuidadora(id_usuario=u.id_usuario, zona=zonas[i % len(zonas)],
                                   especialidades="alzheimer,movilidad reducida" if i % 2 else "postoperatorio,diabetes",
                                   idiomas="español" if i % 3 else "español,inglés",
                                   certificaciones_verificadas=0 if i == 3 else 1 + i % 3,
                                   calificacion_promedio=round(4 + rnd.random(), 2) if estado != "pendiente" else None,
                                   estado_publicacion=estado,
                                   motivo_estado="Certificado de primeros auxilios vencido." if estado == "suspendido" else None,
                                   fecha_envio=now - timedelta(days=rnd.randint(1, 40)),
                                   fecha_revision=now - timedelta(days=1) if estado != "pendiente" else None,
                                   id_staff_revisor=editora.id_staff if editora and estado != "pendiente" else None))
        hechos.append("perfiles de cuidadoras")

    if _vacia(db, ElementoModeracion) and len(usuarios) > 4:
        items = [("resena", "★☆☆☆☆ La cuidadora llegó tarde tres veces y fue grosera con mi madre.", "Lenguaje inapropiado", False),
                 ("foto", "[foto] Celebración de cumpleaños de don Raúl con la familia.", "Muestra datos de otra persona", False),
                 ("mensaje", "Compra seguidores baratos en www.spam-ejemplo.com", "Spam", False),
                 ("resena", "★★★★★ Excelente servicio, muy puntual y cariñosa.", None, False),
                 ("perfil", "Perfil: «Cuido abuelitos, pago solo en efectivo por fuera de la app».", "Evade la plataforma", True),
                 ("mensaje", "Si no me pagas hoy vas a ver lo que le pasa a tu papá.", "Amenaza", True),
                 ("resena", "★★☆☆☆ La app no me avisó a tiempo de la toma del medicamento.", "Fuera de tema", False),
                 ("foto", "[foto] Receta médica con RUT y diagnóstico visibles.", "Datos sensibles", False)]
        for i, (tipo, cont, motivo, seg) in enumerate(items):
            autor, rep = usuarios[i % len(usuarios)], usuarios[(i + 3) % len(usuarios)]
            db.add(ElementoModeracion(id_usuario_autor=autor.id_usuario, id_usuario_reportante=rep.id_usuario if motivo else None,
                                      tipo_elemento=tipo, contenido_reportado=cont, motivo_reporte=motivo,
                                      es_reporte_seguridad=seg, fecha_creacion=now - timedelta(hours=rnd.randint(1, 72))))
        for i in range(6):  # historial ya decidido
            autor = usuarios[(i * 2) % len(usuarios)]
            rech = i % 2 == 0
            db.add(ElementoModeracion(id_usuario_autor=autor.id_usuario, tipo_elemento="resena",
                                      contenido_reportado="Reseña revisada previamente.", estado="rechazado" if rech else "aprobado",
                                      motivo_rechazo="ofensivo" if rech else None,
                                      id_staff_decisor=moderador.id_staff if moderador else None,
                                      fecha_decision=now - timedelta(days=i + 1), fecha_creacion=now - timedelta(days=i + 2)))
        hechos.append("cola de moderación")

    # ---------------------------------------------------------------- cuentas, suscripciones y pagos
    if _vacia(db, CuentaCliente) and usuarios:
        precios = {p.codigo_plan: p.precio for p in db.scalars(select(Plan))}
        familiares = [u for u in usuarios if any(p.codigo_perfil == "familiar" for p in u.perfiles)]
        cuid = [u for u in usuarios if any(p.codigo_perfil == "cuidadora" for p in u.perfiles)]
        ctas = [(u, "familia", f"Familia {u.nombre.split()[-1]}", rnd.choice(["dorado", "dorado", "platino", "gratuito"])) for u in familiares[:10]]
        ctas += [(cuid[0], "proveedor", "Cuidados Andes SpA", "proveedor")] if cuid else []
        ctas += [(cuid[1], "proveedor", "Residencia Los Aromos", "proveedor")] if len(cuid) > 1 else []
        n_tx = 0
        for i, (u, tipo, nombre, plan) in enumerate(ctas):
            inicio = now - timedelta(days=rnd.randint(40, 160))
            c = CuentaCliente(id_usuario=u.id_usuario, tipo_cuenta=tipo, nombre=nombre, email_facturacion=u.email,
                              rut="76.543.210-3" if tipo == "proveedor" and i % 2 else None, fecha_creacion=inicio)
            db.add(c)
            db.flush()
            estado = "activa"
            if i == 3:
                estado = "en_mora"
            if i == 7:
                estado = "cancelada"
            meses = int((now - inicio).days // 30)
            fin = inicio + timedelta(days=30 * (meses + 1))
            s = Suscripcion(id_cuenta=c.id_cuenta, codigo_plan=plan, estado=estado, fecha_inicio=inicio,
                            inicio_periodo=fin - timedelta(days=30), fin_periodo=fin, id_externo_pasarela=f"sub_demo_{c.id_cuenta}",
                            fecha_cancelacion=now - timedelta(days=5) if estado == "cancelada" else None,
                            motivo_cancelacion="El usuario se cambió de servicio." if estado == "cancelada" else None)
            db.add(s)
            db.flush()
            if precios[plan] > 0:
                for m in range(meses + 1):
                    f = inicio + timedelta(days=30 * m)
                    ultimo = m == meses
                    rechazada = ultimo and estado == "en_mora"
                    db.add(TransaccionPago(id_suscripcion=s.id_suscripcion, monto=precios[plan], estado="rechazada" if rechazada else "aprobada",
                                           fecha=f, medio_pago=rnd.choice(["Visa ****4242", "Mastercard ****5100", "Redcompra ****0012"]),
                                           codigo_error="fondos_insuficientes" if rechazada else None,
                                           id_externo_pasarela=f"tx_demo_{s.id_suscripcion}_{m}"))
                    n_tx += 1
        hechos.append(f"{len(ctas)} cuentas de clientes y {n_tx} transacciones")

    # ---------------------------------------------------------------- métricas agregadas (simuladas: vienen de la plataforma)
    if _vacia(db, MetricaDiaria):
        hoy = now.date()
        activos, pago = 4200, 240
        for d in range(400, -1, -1):
            f = hoy - timedelta(days=d)
            crec = 1 + (400 - d) / 400 * 1.4
            estac = 1 + .25 * math.sin((f.timetuple().tm_yday / 365) * 2 * math.pi)
            altas = int(rnd.gauss(28 * crec * estac, 5))
            bajas = int(max(2, rnd.gauss(altas * .14, 2)))
            descargas = int(altas * rnd.uniform(1.8, 2.3))
            activos += altas - bajas
            pago += int(rnd.gauss(altas * .1, 1.2)) - int(rnd.random() < .5)
            mrr = int(pago * 3680)
            db.add(MetricaDiaria(fecha=f, altas=max(altas, 0), bajas=bajas, descargas=descargas, usuarios_activos=activos,
                                 usuarios_pago=pago, mrr=mrr))
        db.flush()
        planes = {p.codigo_plan: p for p in db.scalars(select(Plan))}
        for d in range(35, -1, -1):
            f = hoy - timedelta(days=d)
            md = db.get(MetricaDiaria, f)
            pagos = md.usuarios_pago
            mix = {"gratuito": md.usuarios_activos - pagos, "dorado": int(pagos * .65), "platino": int(pagos * .25)}
            mix["proveedor"] = pagos - mix["dorado"] - mix["platino"]
            churn = {"gratuito": .029, "dorado": .041, "platino": .022, "proveedor": .018}
            for c, n in mix.items():
                precio = planes[c].precio or None
                db.add(SnapshotPlan(fecha=f, codigo_plan=c, usuarios=n, precio_congelado=precio, mrr=n * (precio or 0),
                                    churn_mensual=churn[c]))
            descargas = db.scalar(select(func.sum(MetricaDiaria.descargas)).where(MetricaDiaria.fecha <= f))
            db.add(SnapshotEmbudo(fecha=f, descargas=descargas, cuentas_creadas=int(descargas * .68),
                                  activos_30d=md.usuarios_activos, de_pago=pagos))
        perfiles = {"familiar": (5310, 9.4, 250, .78), "cuidadora": (1470, 22.6, 460, .91),
                    "adulto_mayor": (2640, 11.8, 545, .64), "medico": (420, 2.1, 200, .55)}
        for v, k in ((7, .62), (30, 1.0), (90, 1.31)):
            for c, (a, s, dur, ret) in perfiles.items():
                db.add(ActividadPerfil(ventana_dias=v, codigo_perfil=c, usuarios_activos=int(a * k), sesiones_semana=s,
                                       duracion_media_seg=dur, retencion_30d=ret))
        heat = {  # wireframe v1: familiar, cuidadora, adulto mayor, médico (None = no aplica)
            "inicio_semaforo": (92, 88, None, 61), "centro_alertas": (84, 71, None, 33), "vitals": (77, 64, None, 58),
            "medicamentos": (69, 91, None, 72), "checkin": (None, 86, None, None), "bitacora": (48, 83, None, 39),
            "chat": (62, 55, 47, 12), "asistente_ia": (41, 18, None, 9), "fotos": (58, 22, 66, None),
            "entretenimiento": (None, None, 54, None), "director_musical": (21, None, 38, None),
            "documentos": (34, 29, None, 44), "reportes": (9, 13, None, 7), "marketplace": (11, 6, None, None),
            "sos": (None, 4, 2, None)}
        orden = ["familiar", "cuidadora", "adulto_mayor", "medico"]
        for v, k in ((7, .82), (30, 1.0), (90, 1.08)):
            for f, vals in heat.items():
                for c, pct in zip(orden, vals):
                    if pct is None:
                        continue
                    base = int(perfiles[c][0] * (.62 if v == 7 else 1.31 if v == 90 else 1))
                    ad = min(.99, pct / 100 * k)
                    db.add(AdopcionFuncionalidad(ventana_dias=v, codigo_funcionalidad=f, codigo_perfil=c,
                                                 usuarios=int(base * ad), activos_del_perfil=base, adopcion=round(ad, 5)))
        hechos.append("métricas agregadas (400 días)")
    consolidar_soporte(db)

    # ---------------------------------------------------------------- legales
    if _vacia(db, VersionLegal) and admin:
        texto = ("Estos términos regulan el uso de la plataforma AgeCare por parte de familiares, cuidadoras, médicos y "
                 "adultos mayores. El servicio entrega información de apoyo al cuidado y no reemplaza la atención médica. ") * 3
        priv = ("AgeCare trata datos de salud con el consentimiento del titular o de su representante, solo para entregar "
                "el servicio de cuidado. Los datos se almacenan cifrados y no se venden a terceros. ") * 3
        db.add_all([
            VersionLegal(id_staff_autor=admin.id_staff, tipo_documento="terminos", version_mayor=1, version_menor=0, contenido=texto,
                         registro_cambios="Versión inicial para la publicación en tiendas.", fecha_vigencia=date(2026, 8, 1),
                         requiere_reaceptacion=True, estado="publicada", fecha_publicacion=now - timedelta(days=70)),
            VersionLegal(id_staff_autor=admin.id_staff, tipo_documento="privacidad", version_mayor=1, version_menor=0, contenido=priv,
                         registro_cambios="Versión inicial conforme a la Ley 19.628.", fecha_vigencia=date(2026, 8, 1),
                         requiere_reaceptacion=True, estado="publicada", fecha_publicacion=now - timedelta(days=70)),
        ])
        hechos.append("términos y privacidad v1.0")

    # ---------------------------------------------------------------- avisos de salud por WhatsApp (v0.5.0)
    if _vacia(db, MensajeWhatsapp) and usuarios:
        from app import whatsapp as wa
        familiares = [u for u in usuarios if any(m.rol_en_circulo == "familiar" for m in u.membresias)]
        con_plan = [u for u in familiares if any(wa.plan_incluye_whatsapp(db, wa.plan_del_paciente(db, m.id_paciente))
                                                 for m in u.membresias)]
        sin_whatsapp = con_plan[2] if len(con_plan) > 2 else None  # un número sin WhatsApp para ver avisos fallidos
        for i, u in enumerate(familiares):
            if u.telefono is None:
                u.telefono = "+56900000000" if u is sin_whatsapp else f"+569{rnd.randint(10_000_000, 99_999_999)}"
                u.whatsapp_habilitado = i % 5 != 4 or u is sin_whatsapp  # 4 de cada 5 familiares autorizaron
                u.whatsapp_verificado = u.fecha_registro + timedelta(days=2) if u.whatsapp_habilitado else None
        db.flush()
        criticas = db.scalars(select(Alerta).where(Alerta.severidad == "critica", Alerta.fecha_emision >= now - timedelta(days=7))
                              .order_by(Alerta.fecha_emision)).all()
        n = 0
        for a in criticas:
            for m in wa.encolar_avisos(db, a, ahora=a.fecha_emision):
                n += 1
                if m.estado != "pendiente":
                    continue
                m.intentos, m.proximo_intento = 1, None
                if m.telefono.endswith("0000"):
                    m.estado, m.intentos, m.motivo = "fallido", 3, "Simulación: el número no tiene WhatsApp o no está disponible."
                    continue
                m.estado, m.id_mensaje_proveedor = "enviado", f"wamid.SIMseed{m.id_mensaje:06d}"
                m.fecha_envio = a.fecha_emision + timedelta(seconds=rnd.uniform(1, 4))
                if a.fecha_emision < now - timedelta(minutes=5):
                    m.estado, m.fecha_entrega = "entregado", m.fecha_envio + timedelta(seconds=rnd.uniform(2, 12))
                    if rnd.random() < .75:
                        m.estado, m.fecha_lectura = "leido", m.fecha_entrega + timedelta(minutes=rnd.uniform(.5, 25))
        hechos.append(f"{n} avisos por WhatsApp a familiares")
    db.commit()
    return hechos
