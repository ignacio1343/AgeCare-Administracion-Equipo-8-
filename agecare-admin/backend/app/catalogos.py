"""Datos de catálogo fijos: roles, matriz de permisos (spec 2.3), perfiles de la app y categorías."""
ROLES = [
    ("admin", "Administrador", "Acceso total a la consola."),
    ("analista", "Analista", "Lee métricas, estado operativo y soporte; no modifica."),
    ("soporte", "Agente de soporte", "Atiende tickets, usuarios de la app e incidentes."),
    ("editor", "Editor de contenido", "Cura contenidos, productos y perfiles de cuidadoras."),
    ("moderador", "Moderador", "Revisa contenido reportado."),
]

# módulo -> {rol: nivel}. Sin entrada = sin acceso.
MATRIZ = {
    "metricas":      {"admin": "escritura", "analista": "lectura", "soporte": "lectura"},
    "operacion":     {"admin": "escritura", "analista": "lectura", "soporte": "escritura"},
    "soporte":       {"admin": "escritura", "analista": "lectura", "soporte": "escritura"},
    "usuarios":      {"admin": "escritura", "soporte": "escritura"},
    "contenido":     {"admin": "escritura", "editor": "escritura"},
    "marketplace":   {"admin": "escritura", "editor": "escritura", "moderador": "lectura"},
    "moderacion":    {"admin": "escritura", "moderador": "escritura"},
    "comercial":     {"admin": "escritura", "analista": "lectura"},
    "configuracion": {"admin": "escritura"},
    "staff":         {"admin": "escritura"},
}

PERFILES_APP = [("familiar", "Familiar"), ("cuidadora", "Cuidadora"), ("adulto_mayor", "Adulto mayor"), ("medico", "Médico")]

CATEGORIAS = [
    ("acceso_cuenta", "Acceso y cuenta"), ("wearable", "Wearable y sincronización"), ("alertas_push", "Alertas y push"),
    ("pagos_planes", "Pagos y planes"), ("medicamentos", "Medicamentos"), ("otros", "Otros"),
]


def cargar_catalogos(db) -> None:
    from .models import CategoriaTicket, PerfilApp, PermisoRol, RolStaff
    for c, n, d in ROLES:
        if db.get(RolStaff, c) is None:
            db.add(RolStaff(codigo_rol=c, nombre=n, descripcion=d))
    db.flush()
    for modulo, por_rol in MATRIZ.items():
        for rol, nivel in por_rol.items():
            p = db.get(PermisoRol, (modulo, rol))
            if p is None:
                db.add(PermisoRol(modulo=modulo, codigo_rol=rol, nivel_acceso=nivel))
            else:
                p.nivel_acceso = nivel
    for c, n in PERFILES_APP:
        if db.get(PerfilApp, c) is None:
            db.add(PerfilApp(codigo_perfil=c, nombre=n))
    for c, n in CATEGORIAS:
        if db.get(CategoriaTicket, c) is None:
            db.add(CategoriaTicket(codigo_categoria=c, nombre=n))
    db.flush()
    cargar_catalogos_modulos(db)


# ---------------------------------------------------------------- catálogos de los demás módulos
COMPONENTES = [  # codigo, nombre, tecnología, asíncrono, umbral p95 (ms)
    ("api_core", "API central", "FastAPI · Container Apps", False, 400),
    ("database", "Base de datos", "PostgreSQL Flexible", False, 100),
    ("auth", "Autenticación", "JWT · gestión de sesiones", False, 500),
    ("push", "Notificaciones push", "Notification Hubs (entrega extremo a extremo)", True, 4500),
    ("alert_engine", "Motor de alertas", "Reglas + jobs programados", False, 1000),
    ("wearable_ingest", "Ingesta wearables", "API batch de signos vitales", False, 600),
    ("ai_assistant", "Asistente IA", "LLM · resúmenes y consultas (generación)", True, 3200),
    ("storage", "Almacenamiento", "Blob · documentos y audio", False, 700),
    ("music_sync", "Sync Director Musical", "Cola offline-first", False, 900),
]
PROCESOS = [  # codigo, nombre, cadena, componentes, p95 s, éxito 24 h
    ("caida", "Alerta de caída", "Wearable → ingesta → motor de alertas → push familiar",
     ["wearable_ingest", "alert_engine", "push"], 6.8, .997),
    ("sos", "Botón SOS", "App → API → push a círculo de cuidado", ["api_core", "push"], 3.1, .999),
    ("medicamento", "Alerta de medicamento omitido", "Ventana de toma → job programado → push", ["alert_engine", "push"], 48, .995),
    ("ia", "Consulta al asistente IA", "App → API → LLM → respuesta", ["api_core", "ai_assistant"], 4.2, .978),
    ("musica", "Sincronización Director Musical", "Tablet → API → almacenamiento → confirmación",
     ["api_core", "storage", "music_sync"], 11.4, .992),
]
TIPOS_ALERTA = [("caida", "Caída detectada", "critica"), ("sos", "Botón SOS", "critica"),
                ("vital", "Signo vital fuera de rango", "alta"), ("medicamento", "Medicamento omitido", "media")]
UMBRALES = [  # signo, nivel, min, max, unidad   (fuera del rango amarillo = rojo -> alerta)
    ("frecuencia_cardiaca", "verde", 60, 100, "lpm"), ("frecuencia_cardiaca", "amarillo", 50, 120, "lpm"),
    ("saturacion_o2", "verde", 95, 100, "%"), ("saturacion_o2", "amarillo", 90, 100, "%"),
    ("presion_sistolica", "verde", 90, 139, "mmHg"), ("presion_sistolica", "amarillo", 85, 159, "mmHg"),
    ("temperatura", "verde", 36, 37.5, "°C"), ("temperatura", "amarillo", 35.5, 38, "°C"),
]
PLANES = [("gratuito", "Gratuito", 0, "usuario"), ("dorado", "Dorado", 1000, "usuario"),
          ("platino", "Platino", 10000, "familia"), ("proveedor", "Proveedor", 5000, "proveedor")]
FUNCIONALIDADES = [  # codigo, nombre, uso bajo esperado, nota
    ("inicio_semaforo", "Inicio / semáforo", False, None), ("centro_alertas", "Centro de alertas", False, None),
    ("vitals", "Vitals del wearable", False, None), ("medicamentos", "Medicamentos y adherencia", False, None),
    ("checkin", "Check-in diario", False, None), ("bitacora", "Bitácora y observaciones", False, None),
    ("chat", "Chat de coordinación", False, None), ("asistente_ia", "Asistente IA", False, None),
    ("fotos", "Fotos compartidas", False, None), ("entretenimiento", "Entretenimiento", False, None),
    ("director_musical", "Director Musical", False, None), ("documentos", "Documentos médicos", False, None),
    ("reportes", "Reportes (premium)", False, None), ("marketplace", "Marketplace", False, None),
    ("sos", "SOS", True, "Uso bajo por diseño: es un evento de emergencia."),
    ("alertas_whatsapp", "Avisos de salud por WhatsApp al familiar", True,
     "Uso bajo por diseño: solo se envía ante eventos de riesgo."),
]
_BASE = ["inicio_semaforo", "centro_alertas", "vitals", "medicamentos", "checkin", "bitacora", "chat", "fotos",
         "entretenimiento", "sos", "marketplace"]
PLAN_FUNCIONALIDADES = {
    "gratuito": _BASE,
    "dorado": _BASE + ["asistente_ia", "documentos", "director_musical"],
    "platino": _BASE + ["asistente_ia", "documentos", "director_musical", "reportes", "alertas_whatsapp"],
    "proveedor": [f[0] for f in FUNCIONALIDADES],
}
PARAMETROS = [  # clave, descripción, categoría, tipo, valor
    ("objetivo_primera_respuesta_horas", "Objetivo de horas para la primera respuesta a un ticket (OE1).", "soporte", "numero", "4"),
    ("dias_cierre_automatico_tickets", "Días tras «resuelto» para cerrar el ticket automáticamente.", "soporte", "numero", "7"),
    ("churn_dias_inactividad", "Días sin actividad para considerar a un usuario como baja.", "metricas", "numero", "30"),
    ("alerta_medicamento_minutos_gracia", "Minutos de gracia antes de alertar un medicamento no confirmado.", "alertas", "numero", "30"),
    ("alerta_caida_escalamiento_min", "Minutos sin atención para escalar una alerta de caída al segundo contacto.", "alertas", "numero", "5"),
    ("semaforo_horas_sin_datos", "Horas sin datos del wearable para pasar el semáforo a amarillo.", "alertas", "numero", "6"),
    ("monitor_fallos_para_caida", "Verificaciones fallidas seguidas para marcar un componente como caído.", "operacion", "numero", "3"),
    ("modo_mantenimiento", "Muestra un aviso de mantenimiento en la app.", "sistema", "booleano", "false"),
    ("mensaje_bienvenida_app", "Mensaje que ve el usuario al abrir la app.", "sistema", "texto", "Bienvenido a AgeCare"),
    ("whatsapp_activo", "Envía avisos por WhatsApp a los familiares ante eventos de salud de riesgo.", "whatsapp", "booleano", "true"),
    ("whatsapp_minutos_entre_avisos", "Minutos mínimos entre dos avisos al mismo familiar por el mismo paciente (evita saturar).", "whatsapp", "numero", "30"),
    ("whatsapp_max_intentos", "Intentos de envío antes de marcar un aviso como fallido.", "whatsapp", "numero", "3"),
    ("whatsapp_incluir_valor", "Incluye el valor medido del signo vital en el mensaje.", "whatsapp", "booleano", "true"),
]


def cargar_catalogos_modulos(db) -> None:
    from .models import (Componente, ComponenteProceso, Funcionalidad, ParametroSistema, Plan, PlanFuncionalidad,
                         ProcesoCritico, TipoAlerta, UmbralAlerta)
    for i, (c, n, t, a, u) in enumerate(COMPONENTES):
        if db.get(Componente, c) is None:
            db.add(Componente(codigo_componente=c, nombre=n, tecnologia=t, es_asincrono=a, umbral_p95_ms=u, orden=i))
    for i, (c, n, cad, comps, p95, ex) in enumerate(PROCESOS):
        if db.get(ProcesoCritico, c) is None:
            db.add(ProcesoCritico(codigo_proceso=c, nombre=n, cadena=cad, p95_segundos=p95, exito_24h=ex, orden=i))
            db.flush()
            for comp in comps:
                db.add(ComponenteProceso(codigo_componente=comp, codigo_proceso=c))
    for c, n, s in TIPOS_ALERTA:
        if db.get(TipoAlerta, c) is None:
            db.add(TipoAlerta(codigo_tipo=c, nombre=n, severidad_por_defecto=s))
    db.flush()
    for s, nivel, mn, mx, u in UMBRALES:
        if db.get(UmbralAlerta, (s, nivel)) is None:
            db.add(UmbralAlerta(signo_vital=s, nivel_semaforo=nivel, codigo_tipo="vital", valor_minimo=mn, valor_maximo=mx, unidad=u))
    nuevas = []
    for i, (c, n, b, nota) in enumerate(FUNCIONALIDADES):
        if db.get(Funcionalidad, c) is None:
            db.add(Funcionalidad(codigo_funcionalidad=c, nombre=n, uso_bajo_esperado=b, nota=nota, orden=i))
            nuevas.append(c)
    for i, (c, n, precio, unidad) in enumerate(PLANES):
        if db.get(Plan, c) is None:
            db.add(Plan(codigo_plan=c, nombre=n, precio=precio, unidad_facturable=unidad, orden=i))
            db.flush()
            for f in PLAN_FUNCIONALIDADES[c]:
                db.add(PlanFuncionalidad(codigo_plan=c, codigo_funcionalidad=f))
        elif nuevas:  # base existente: una funcionalidad nueva se asigna a los planes que la incluyen por defecto
            db.flush()
            for f in nuevas:
                if f in PLAN_FUNCIONALIDADES[c] and db.get(PlanFuncionalidad, (c, f)) is None:
                    db.add(PlanFuncionalidad(codigo_plan=c, codigo_funcionalidad=f))
    for clave, d, cat, tipo, val in PARAMETROS:
        if db.get(ParametroSistema, clave) is None:
            db.add(ParametroSistema(clave=clave, descripcion=d, categoria=cat, tipo_valor=tipo, valor=val))
    db.flush()
