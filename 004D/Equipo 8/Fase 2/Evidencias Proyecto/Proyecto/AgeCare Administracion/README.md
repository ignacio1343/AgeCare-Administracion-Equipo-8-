# AgeCare · Consola de Administración — Avance 2 + módulos de Sprints 3 a 5

Portal web interno para que el equipo de Wellq Co opere la plataforma AgeCare. Este repositorio contiene el
**Avance 2** comprometido en la Guía Fase 1 (seguridad, staff, auditoría y soporte) **y los módulos de los
Sprints 3 a 5**: usuarios de la app, estado operativo, contenidos y marketplace, moderación, dashboards,
planes y suscripciones, configuración y documentos legales. Los 40 casos de uso del diagrama general v2 tienen
pantalla y endpoint.

| Capa | Tecnología |
| --- | --- |
| Frontend | React 18 + Vite + TypeScript (SPA) |
| Backend | Python 3.12 + FastAPI + SQLAlchemy 2 + Alembic |
| Base de datos | PostgreSQL 16 |
| Seguridad | JWT (15 min) + refresh token rotatorio (12 h), Argon2id, TOTP (2FA), control de acceso por rol |
| Contenedores | Docker Compose (db + api + web con nginx) |
| Publicación | Render (API Docker + sitio estático) y Neon (PostgreSQL) |

## Qué incluye

Cada pantalla y endpoint responde a un caso de uso del diagrama general v2:

| Caso de uso | Dónde | Estado |
| --- | --- | --- |
| CU01 Iniciar sesión | `/login` · `POST /auth/login` | ✔ con bloqueo tras 5 intentos fallidos en 10 min (15 min) |
| CU02 Verificar segundo factor | `/perfil` · `/auth/mfa/*` | ✔ TOTP con QR; obligatorio para el rol admin |
| CU03 Gestionar cuentas y roles del staff | `/staff` · `/staff` | ✔ crear con invitación, cambiar rol, desactivar, reenviar enlace |
| CU04 Consultar bitácora de auditoría | `/auditoria` · `GET /auditoria` | ✔ toda escritura y todo login quedan registrados (OE4) |
| CU25 Consultar indicadores de soporte | `/soporte` · `GET /soporte/indicadores` | ✔ abiertos, en curso, resueltos 30 d, primera respuesta (OE1), CSAT |
| CU35 Consultar cola de tickets | `/soporte` · `GET /soporte/tickets` | ✔ filtros, búsqueda por #número/asunto/correo, orden, paginación |
| CU36 Registrar ticket | `/soporte/nuevo` · `POST /soporte/tickets` | ✔ enlaza al usuario de la app o crea sin enlazar |
| CU37 Atender ticket | `/soporte/:id` · `PATCH /soporte/tickets/{id}` | ✔ transiciones válidas, asignación, prioridad, categoría |
| CU38 Consultar contexto del solicitante | detalle del ticket | ✔ perfil, pacientes, tickets previos |
| CU39 Responder ticket | `POST /soporte/tickets/{id}/respuestas` | ✔ respuesta pública o nota interna |
| CU40 Enviar encuesta de satisfacción | al pasar a «resuelto» | ✔ envío simulado; se muestra el puntaje |

### Sprints 3 a 5

| Caso de uso | Dónde | Qué hace |
| --- | --- | --- |
| CU05 Configurar umbrales de alertas | `/configuracion` → Umbrales · `PUT /configuracion/umbrales/{signo}/{nivel}` | semáforo verde/amarillo/rojo por signo vital; valida rangos |
| CU06 Configurar parámetros del sistema | `/configuracion` → Parámetros · `PUT /configuracion/parametros/{clave}` | valor tipado, nota obligatoria, versión (avisa si otra persona lo cambió) |
| CU07 Redactar versión legal | `/configuracion` → Documentos legales · `POST/PATCH /legales/versiones` | borrador de términos o privacidad; versión semántica automática |
| CU08 Publicar versión legal | `POST /legales/versiones/{id}/publicar` | reemplaza la vigente; la publicada no se edita; `GET /legales/publico/{tipo}` la entrega a la app |
| CU09 Configurar planes | `/planes` → Planes · `PUT /comercial/planes/{codigo}` | precio, nombre, funcionalidades incluidas; el plan gratuito siempre vale $0 |
| CU10 Gestionar cuentas de clientes | `/planes` → Cuentas · `/comercial/cuentas` | alta con titular de la app, RUT validado, plan inicial |
| CU11 Cambiar plan | `/planes` → Suscripciones · `PATCH /comercial/suscripciones/{id}/plan` | |
| CU12 Cancelar suscripción | `POST /comercial/suscripciones/{id}/cancelar` | con motivo; se informa a la pasarela (simulada) |
| CU13 Consultar transacciones | `/planes` → Transacciones · `GET /comercial/transacciones` | |
| CU14 Registrar evento de pago | `POST /pagos/webhook` (firma HMAC) · `/planes` → Eventos | idempotente: un evento repetido no se procesa dos veces |
| CU15 Emitir reembolso | `POST /comercial/transacciones/{id}/reembolsos` | total o parcial, nunca más de lo cobrado |
| CU16 Moderar contenido reportado | `/moderacion` · `/moderacion/cola` · `/moderacion/{id}/decision` | reportes de seguridad primero; rechazo con motivo |
| CU17 Gestionar contenido curado | `/contenidos` · `/contenidos` | chistes y noticias en borrador, edición, borrado lógico |
| CU18 Publicar o programar contenido | `POST /contenidos/{id}/publicar` | ahora o en una fecha; el planificador publica los programados |
| CU19 Gestionar productos de apoyo | `/contenidos` → Productos · `/productos` | enlace externo solo https |
| CU20 Revisar perfiles de cuidadoras | `/contenidos` → Cuidadoras · `/cuidadoras/{id}/revision` | aprobar exige certificación verificada; suspender exige motivo |
| CU21 Métricas comerciales | `/dashboards` · `/metricas/comerciales` · `/metricas/planes` | KPIs por periodo con variación, altas/bajas, mezcla de planes, MRR |
| CU22 Embudo freemium | `/metricas/embudo` | descargas → cuentas → activos → pago |
| CU23 Métricas por perfil | `/metricas/perfiles` | familiar, cuidadora, adulto mayor, médico |
| CU24 Adopción de funcionalidades | `/metricas/adopcion` | mapa de calor perfil × funcionalidad con alertas bajo 15% |
| CU26 Consolidar métricas | `POST /metricas/consolidar` · planificador | genera `METRICA_SOPORTE_DIARIA` desde los tickets |
| CU27 Monitorear componentes | `/estado` · planificador cada 60 s | p50/p95 y uptime 30 d por componente |
| CU28 Abrir incidente automático | monitor | tras 3 fallas seguidas el componente pasa a «caído» y se abre un incidente |
| CU29 Consultar estado operativo | `/estado` · `GET /operacion/estado` | componentes y procesos críticos de cuidado |
| CU30 Monitorear alertas | `GET /operacion/alertas` | alertas de pacientes por tipo y tiempo de atención |
| CU31 Gestionar incidentes | `/operacion/incidentes` | registrar, actualizar, resolver (exige resolución) |
| CU32 Buscar usuarios y pacientes | `/usuarios` · `GET /usuarios` | por nombre, correo o paciente |
| CU33 Desactivar o reactivar cuenta | `PATCH /usuarios/{id}/estado` | con motivo en la auditoría |
| CU34 Reenviar invitación al círculo | `POST /usuarios/{id}/membresias/{id_paciente}/invitacion` | |

**Para probar el monitor:** en «Estado operativo» elige «Simular falla: Notificaciones push» y presiona
«Ejecutar ciclo del monitor» tres veces. El componente pasa a caído y aparece un incidente abierto por el monitor.

Capturas en [`docs/capturas`](docs/capturas). Diagrama de casos de uso y MER en [`docs`](docs).

## Cómo levantarlo

### Opción A · Docker (recomendada)

```bash
docker compose up --build
```

- Consola: <http://localhost:8080>
- API y documentación interactiva (Swagger): <http://localhost:8000/api/v1/docs>

El contenedor de la API aplica la migración y carga los datos demo automáticamente.

### Opción B · Windows con VS Code (paso a paso)

Requisitos: **Python 3.12** y **Node.js 20 LTS** (descárgalo de <https://nodejs.org>, instala con las opciones
por defecto y **cierra y vuelve a abrir VS Code** para que reconozca `npm`).

Terminal 1 (PowerShell), el backend:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
copy .env.example .env
# Para la prueba rápida sin PostgreSQL, abre .env y deja: DATABASE_URL=sqlite:///./agecare.db
python -m scripts.seed
uvicorn app.main:app --reload
```

Terminal 2 (el «+» del panel de terminal), el frontend:

```powershell
cd frontend
npm install
npm run dev
```

Abre <http://localhost:5173> e ingresa con `admin@wellq.co.uk` / `Admin123!`.

- Si PowerShell no deja activar el entorno, ejecuta una vez
  `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` y responde «S».
- **¿Ya tenías la base del Avance 2?** Con SQLite basta con `python -m scripts.seed`: crea las tablas nuevas y
  carga sus datos sin tocar los tickets. Con PostgreSQL ejecuta primero `alembic upgrade head`.
  Para empezar de cero: `python -m scripts.seed --reset`.

### Opción C · Manual en Linux o macOS

Requisitos: Python 3.12+, Node 20+ y un PostgreSQL 16 con una base `agecare_admin`.

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate      # en Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                                    # ajusta DATABASE_URL
alembic upgrade head                                    # crea las tablas
python -m scripts.seed                                  # datos demo (usa --reset para reiniciarlos)
uvicorn app.main:app --reload                           # http://localhost:8000

# Frontend (otra terminal)
cd frontend
npm install
npm run dev                                             # http://localhost:5173
```

> ¿Sin PostgreSQL a mano? Para una prueba rápida, en `.env` usa `DATABASE_URL=sqlite:///./agecare.db`
> y salta `alembic upgrade head` (el seed crea las tablas).

## Despliegue en Render + Neon (gratuito)

La consola se publica en **Render** (API como contenedor Docker y consola como sitio estático) con la base de
datos **PostgreSQL en Neon**. Todo se define en [`render.yaml`](render.yaml).

1. **Neon:** crea una cuenta en <https://neon.com> (sin tarjeta), un proyecto en la región *AWS US East (N. Virginia)*
   y copia la *connection string* (`postgresql://usuario:clave@ep-....neon.tech/neondb?sslmode=require`).
2. **Render:** crea una cuenta en <https://render.com> con GitHub → *New* → *Blueprint* → elige este repositorio.
   Render lee `render.yaml` y crea `agecare-admin-api` y `agecare-admin`.
3. Cuando lo pida, pega la connection string de Neon en `DATABASE_URL`. `JWT_SECRET` y `PASARELA_WEBHOOK_SECRET`
   se generan solos.
4. Espera el primer despliegue: la API aplica las migraciones y carga los datos demo al iniciar.
   Consola: `https://agecare-admin.onrender.com` · API: `https://agecare-admin-api.onrender.com/api/v1/docs`.
5. Si Render asigna otros nombres, ajusta `VITE_API_URL` (sitio estático) y `FRONTEND_URL` / `CORS_ORIGINS` (API).

Cada push a `main` vuelve a desplegar. **Límites del plan gratuito:** la API se suspende tras 15 minutos sin visitas
y tarda cerca de 1 minuto en despertar (ábrela unos minutos antes de una demo); mientras duerme, el planificador
(monitor de componentes) no corre. Neon suspende la base tras 5 minutos sin uso. No uses servicios de «ping» para
mantenerla despierta: el planificador consultaría la base cada minuto y se agotarían las horas gratuitas de Neon.

## Cuentas demo

| Correo | Contraseña | Rol | Ve |
| --- | --- | --- | --- |
| admin@wellq.co.uk | Admin123! | Administrador | Todo |
| soporte@wellq.co.uk | Soporte123! | Agente de soporte | Soporte (escritura), usuarios, estado, dashboards |
| analista@wellq.co.uk | Analista123! | Analista | Soporte y métricas (solo lectura) |
| editora@wellq.co.uk | Editora123! | Editor de contenido | Contenidos y productos (sin acceso a soporte) |
| moderador@wellq.co.uk | Moderador123! | Moderador | Moderación |

El admin tiene el segundo factor *requerido* pero aún no configurado: la consola muestra un aviso y lo puede
activar en «Mi cuenta». Una vez activo, el login le pedirá el código de 6 dígitos.

**Invitar a alguien:** en «Staff y roles» → «Nueva cuenta». El envío por correo está simulado: la consola
muestra el enlace de activación (válido 24 h) para copiarlo.

## Pruebas

```bash
cd backend
pytest                                   # 45 pruebas (35 de integración + 10 unitarias), sobre SQLite
pytest --cov=app                         # con cobertura (90%)
TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/agecare_test pytest   # sobre PostgreSQL
```

Cubren: login y errores genéricos, bloqueo por intentos, rotación de refresh y detección de reuso, logout,
flujo TOTP completo, invitación y activación, reglas de staff (no desactivarse, último admin), revocación de
sesiones, permisos por rol (lectura/escritura/sin acceso), transiciones de ticket, primera respuesta, encuesta,
búsqueda y registro en auditoría; y en los módulos nuevos: monitor e incidente automático, transiciones de
incidente, contenido programado, reglas de cuidadoras y moderación, planes (gratuito en $0), cuentas con RUT,
webhook firmado e idempotente, reembolsos con tope, parámetros con versión y publicación de versiones legales.

## Calidad y seguridad

```bash
cd backend
bandit -r app -q                          # análisis estático: 0 hallazgos altos o medios
pip-audit -r requirements.txt             # dependencias del backend: sin vulnerabilidades conocidas
locust -f tests/locustfile.py --headless -u 50 -r 10 -t 60s --host http://localhost:8000   # carga, API con datos demo
cd ../frontend && npm audit               # quedan avisos moderados/bajos que requieren react-router v7 (Sprint 6)
```

Resultados de la última ejecución (Sprint 4) en [`docs/pruebas`](docs/pruebas): p95 entre 28 y 89 ms en las
consultas principales con 50 usuarios y 0 errores. El detalle está en el Plan de Pruebas (C2).

## Variables de entorno

Ver `backend/.env.example`. Además de las ya descritas: `ZONA_HORARIA` (por defecto `America/Santiago`) define
el «hoy» para la vigencia de documentos legales y las métricas diarias.

## Estructura

```
backend/
  app/
    main.py          arranque FastAPI, CORS, routers
    models.py        tablas (nombres del MER v2)
    security.py      Argon2id, JWT, refresh tokens, TOTP
    deps.py          staff autenticado + requiere(modulo, nivel)  ← control de acceso por rol
    audit.py         registrar() en la bitácora
    catalogos.py     roles, matriz de permisos, perfiles y categorías
    monitor.py       ciclo del monitor de componentes (CU27/28)
    pasarela.py      pasarela de pagos simulada + firma HMAC del webhook
    metricas_job.py  consolidación de métricas (CU26)
    planificador.py  hilo en segundo plano: monitor, publicaciones programadas, cierre de tickets, métricas
    routers/         auth · staff · soporte · usuarios · operacion · contenido · moderacion · metricas
                     · comercial · configuracion
  alembic/           migraciones (0001 Avance 2, 0002 módulos de Sprints 3 a 5)
  scripts/           seed.py y seed_modulos.py (datos demo) · jobs.py · webhook_demo.py
  tests/             pytest (integración y unitarias) · locustfile.py (carga)
frontend/
  src/api.ts         cliente HTTP con renovación automática de sesión
  src/auth.tsx       contexto de sesión y permisos
  src/App.tsx        rutas protegidas por rol
  src/components/    Layout (menú por rol), ui (tablas, chips, formato), charts (gráficos SVG)
  src/pages/         Login, Activar, Perfil, Soporte, TicketNuevo, TicketDetalle, Staff, Auditoria, Usuarios,
                     Estado, Contenidos, Moderacion, Dashboards, Planes, Configuracion
docker-compose.yml
```

## API

Todas las rutas cuelgan de `/api/v1`. Errores con formato único:
`{"error": {"code", "message", "details", "request_id"}}` (códigos como `INVALID_CREDENTIALS`, `ACCOUNT_LOCKED`,
`OTP_REQUIRED`, `INVALID_TRANSITION`, `TICKET_CLOSED`, `LAST_ADMIN`…). Detalle en Swagger.

| Método y ruta | Rol mínimo |
| --- | --- |
| `POST /auth/login` · `/auth/refresh` · `GET /auth/activacion/{token}` · `POST /auth/activacion` | público |
| `GET /auth/me` · `POST /auth/logout` · `POST /auth/mfa/configurar` · `/auth/mfa/confirmar` | autenticado |
| `GET /staff` · `/staff/roles` · `POST /staff` · `PATCH /staff/{id}` · `POST /staff/{id}/invitacion` · `GET /auditoria` | admin |
| `GET /soporte/indicadores` · `/soporte/tickets` · `/soporte/tickets/{id}` · `/respuestas` · `/categorias` · `/agentes` | soporte lectura (admin, soporte, analista) |
| `POST /soporte/tickets` · `PATCH /soporte/tickets/{id}` · `POST /soporte/tickets/{id}/respuestas` | soporte escritura (admin, soporte) |
| `/usuarios/*` | usuarios (admin, soporte) |
| `/operacion/*` | operacion: lectura admin, soporte, analista · escritura admin, soporte |
| `/contenidos/*` | contenido (admin, editor) |
| `/productos/*` · `/cuidadoras/*` | marketplace: escritura admin, editor · lectura moderador |
| `/moderacion/*` | moderacion (admin, moderador) |
| `/metricas/*` | metricas: lectura admin, analista, soporte · consolidar solo admin |
| `/comercial/*` | comercial: escritura admin · lectura analista |
| `/configuracion/*` · `/legales/versiones*` | configuracion (admin) |
| `POST /pagos/webhook` | la pasarela, con cabecera `X-Pasarela-Firma` (HMAC-SHA256 del cuerpo) |
| `GET /legales/publico/{tipo}` | público (lo consume la app) |

## Decisiones y simplificaciones de este avance

- **Modelo de datos:** tablas y columnas con los nombres del MER v2. Se agregaron columnas físicas que el MER
  conceptual no muestra: `password_hash`, `secreto_mfa`, contadores de bloqueo, token de activación y
  `fecha_actualizacion` del ticket.
- **Usuarios y pacientes de la app** son una réplica mínima (sin datos clínicos). En producción los sincroniza
  el planificador desde la Plataforma AgeCare; aquí los carga el seed.
- **Indicadores de soporte** se calculan en vivo sobre los tickets; la serie diaria se guarda en
  `METRICA_SOPORTE_DIARIA` con el job de consolidación.
- **Datos de la plataforma** (métricas de descargas, embudo, adopción, alertas de pacientes, latencias de los
  componentes que no son la base de datos) son simulados por el seed y el monitor, porque vienen de la
  Plataforma AgeCare y de las tiendas de apps, que están fuera del alcance. La verificación de la base de datos
  sí es real.
- **Pasarela de pagos** simulada (`app/pasarela.py`). El webhook valida la firma con `PASARELA_WEBHOOK_SECRET`.
  Para enviar uno de prueba con la API corriendo:
  `python -m scripts.webhook_demo 4 aprobado` (o `rechazado`; el 4 es el id de la suscripción).
- **Correo** (invitaciones, respuestas, encuesta CSAT) está simulado: se registra y se muestra en la consola.
- **Refresh token** se guarda en `localStorage` por simplicidad. Para producción conviene una cookie
  `HttpOnly`, `Secure` y `SameSite=Strict`.
- **Planificador de tareas:** la API corre en segundo plano el monitor (cada `PLANIFICADOR_INTERVALO_SEG`,
  60 s por defecto; `0` lo apaga), publica el contenido programado y una vez por hora cierra los tickets resueltos
  hace más de 7 días y consolida métricas. También se puede ejecutar a mano:
  `python -m scripts.jobs cerrar-tickets | monitor | consolidar`.
