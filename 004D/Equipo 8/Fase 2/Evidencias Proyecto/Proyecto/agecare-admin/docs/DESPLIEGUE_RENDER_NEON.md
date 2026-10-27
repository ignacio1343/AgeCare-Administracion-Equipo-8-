# Publicar AgeCare Admin en Render + Neon (EP10-HU04, HU05 y HU06)

Guía paso a paso para dejar la consola publicada, con despliegue continuo y registros técnicos.
Tiempo estimado: 30 a 45 minutos. Todo es gratuito y no pide tarjeta.

## 0. Antes de empezar

- El código completo (v0.4.0) debe estar en la rama `main` del repositorio de GitHub, incluida la carpeta
  `.github/workflows` y el archivo `render.yaml` en la raíz.
- En GitHub → *Actions*, el workflow **CI** del último push debe estar en verde. Render solo despliega si pasa.

## 1. Base de datos en Neon

1. Entra a <https://neon.com> con tu cuenta de GitHub.
2. *Create project*: nombre `agecare-admin`, PostgreSQL 16, región **AWS US East 1 (N. Virginia)**.
3. En *Connection details* elige la conexión **pooled** y copia la cadena. Tiene esta forma:
   `postgresql://usuario:clave@ep-xxxx-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require`
4. Guárdala en un lugar seguro. **No la subas al repositorio.**

## 2. Servicios en Render (Blueprint)

1. Entra a <https://render.com> con tu cuenta de GitHub y autoriza el acceso al repositorio.
2. *New* → **Blueprint** → elige el repositorio. Render lee `render.yaml` y propone dos servicios:
   - `agecare-admin-api` (web service, Docker, plan free, Virginia).
   - `agecare-admin` (static site).
3. Render pide `DATABASE_URL`: pega la cadena de Neon. `JWT_SECRET` y `PASARELA_WEBHOOK_SECRET` se generan solos.
4. *Apply*. El primer despliegue de la API tarda 5 a 10 minutos: construye la imagen, aplica las migraciones
   (43 tablas) y carga los datos demo.

### Si Render asigna otro nombre a los servicios

El nombre define la URL (`https://<nombre>.onrender.com`). Si `agecare-admin-api` o `agecare-admin` ya estaban
ocupados, Render agrega un sufijo. En ese caso edita `render.yaml`:

- En la API: `FRONTEND_URL` y `CORS_ORIGINS` con la URL real de la consola.
- En el sitio estático: el `destination` de la regla `/api/*` con la URL real de la API.

Haz commit y push; Render aplica el cambio cuando el CI pase.

## 3. Verificar la publicación

| Prueba | Cómo | Resultado esperado |
|---|---|---|
| Health de la API | Abrir `https://agecare-admin-api.onrender.com/api/v1/health` | `{"status":"ok","version":"0.5.1"}` |
| Base de datos | Abrir `https://agecare-admin-api.onrender.com/api/v1/health/db` | `{"status":"ok","db_ms":...}` |
| Rewrite /api | Abrir `https://agecare-admin.onrender.com/api/v1/health` | La misma respuesta que la API |
| Login | Abrir la consola e ingresar con `soporte@wellq.co.uk` / `Soporte123!` | Entra a Soporte |
| Cookie HttpOnly | F12 → *Application* → *Cookies* | `aca_refresh` con *HttpOnly*, *Secure*, *SameSite Strict*, ruta `/api/v1/auth` |
| Sesión persistente | Recargar la página (F5) | Sigue dentro, sin volver al login |
| Permisos | Con `editora@wellq.co.uk`, abrir `/soporte` en la URL | No aparece el módulo / mensaje de permisos |
| Despertar (RNF-10) | Esperar 20 minutos sin uso y abrir la consola | Responde en menos de 1 minuto |

Toma captura de cada resultado: son la evidencia de EP10-HU04 para la Sprint Review.

**Seguridad del piloto:** las contraseñas demo están en el README, que es público. Después de verificar, entra
como admin, configura el segundo factor en *Mi cuenta* y cambia las contraseñas demo, o desactiva en *Staff y
roles* las cuentas que no se usen.

## 4. Despliegue continuo (EP10-HU05)

- Cada push a `main` ejecuta **CI** en GitHub Actions: pruebas sobre PostgreSQL con cobertura mínima de 85 %,
  migraciones sobre una base vacía, bandit, pip-audit, build del frontend, npm audit y construcción de las imágenes
  Docker con prueba del health check.
- `render.yaml` usa `autoDeployTrigger: checksPass`: Render despliega **solo si el CI pasa**. Un push que rompe
  una prueba no llega a producción.
- Evidencia para la Sprint Review: captura de *Actions* con el CI en verde y de *Events* en Render con el deploy
  disparado por ese commit.
- Para volver atrás un despliegue: Render → servicio → *Events* → *Rollback* en un deploy anterior.

## 5. Registros y alertas técnicas (EP10-HU06)

**Registros (Render → `agecare-admin-api` → *Logs*):**

- Cada petición escribe una línea: `INFO acceso: GET /api/v1/soporte/tickets 200 23ms rid=<request_id>`.
- Las peticiones de más de 1 segundo o con error 5xx salen como `WARNING`.
- Los errores no controlados salen como `ERROR errores: ... rid=<request_id>` con su traza.
- Si la base cae, el planificador escribe una sola línea `ERROR planificador: ciclo fallido (1 seguidos): ...`,
  un recordatorio cada 10 ciclos y `planificador recuperado tras N ciclos` al volver (DEF-10).
- Para buscar el error que reportó un usuario, copia el `request_id` que muestra la consola y pégalo en el buscador
  de *Logs* (RNF-24).

**Alertas:**

1. Render → *Workspace settings* → *Notifications*: activa los avisos por correo para los fallos de deploy y de
   servicio (las opciones disponibles dependen del plan).
2. *Health check*: `render.yaml` define `healthCheckPath: /api/v1/health`. Si deja de responder, Render reinicia
   el servicio y lo muestra en *Events*. Este endpoint no consulta la base a propósito, para no mantener Neon
   despierto.
3. Neon → proyecto → *Monitoring*: revisa las horas de cómputo usadas del mes.

**Prueba para la evidencia:** abre `https://agecare-admin-api.onrender.com/api/v1/soporte/tickets/999999` con una
sesión iniciada (o cualquier URL inexistente) y busca su `request_id` en *Logs*.

## 6. Pruebas sobre la nube (EP10-HU07 y HU08, Sprint 6)

Desde GitHub → *Actions* → elige el workflow → *Run workflow*:

- **Prueba de carga:** Locust con 50 usuarios durante 2 minutos contra la URL pública. El resumen queda en la
  página del run (tabla con p95 por endpoint y si cumple RNF-08) y el reporte HTML como artefacto. Si cambiaste la
  contraseña de `analista@wellq.co.uk`, crea los *secrets* `CARGA_EMAIL` y `CARGA_PASSWORD` en *Settings →
  Secrets and variables → Actions*.
- **Seguridad OWASP ZAP:** escaneo *baseline* (pasivo, no modifica datos) de la consola y de la API. Falla si hay
  alertas de riesgo alto (RNF-04). Los reportes HTML quedan como artefactos `zap-consola` y `zap-api`.

Con esos resultados se ejecutan los casos de prueba pendientes CP-19 y CP-20 del Plan de Pruebas.

## 6 bis. Avisos por WhatsApp

La API se publica en modo **simulado** (`WHATSAPP_MODO=simulado`): los avisos se registran y avanzan de estado sin
llamar a Meta. Para enviar mensajes reales sigue [`WHATSAPP.md`](WHATSAPP.md): plantilla aprobada, token, id del
número, *App secret* y webhook `https://agecare-admin-api.onrender.com/api/v1/whatsapp/webhook`.
`PLATAFORMA_API_KEY` la genera Render; cópiala desde *Environment* para la Plataforma AgeCare.

## 7. Problemas frecuentes

| Síntoma | Causa probable | Solución |
|---|---|---|
| El deploy de la API falla en `alembic upgrade head` | `DATABASE_URL` mal copiada | Revisa que termine en `?sslmode=require` y vuelve a desplegar |
| La consola carga pero el login da error de red | La regla `/api/*` apunta a otro nombre de API | Corrige el `destination` en `render.yaml` |
| Login correcto pero al recargar vuelve al login | La cookie no llega (dominios distintos) | Usa el rewrite de `/api/*`. Si no se puede, define `VITE_API_URL` con la URL de la API en el sitio estático, `COOKIE_SAMESITE=none` en la API y agrega la URL de la consola a `CORS_ORIGINS` |
| La primera carga tarda cerca de 1 minuto | El plan gratuito suspendió la API | Normal; abre la consola unos minutos antes de una demo |
| Render no despliega después de un push | El CI falló (`checksPass`) | Revisa el error en GitHub → *Actions* y corrígelo |
| Swagger (`/api/v1/docs`) no carga desde la URL de la consola | La política de seguridad (CSP) del sitio estático bloquea los scripts externos | Ábrelo directo en la URL de la API |

## 8. Reiniciar los datos demo

El plan gratuito de Render no tiene consola (Shell). Desde un computador del equipo, en `backend/` con el entorno
virtual activado:

```powershell
$env:DATABASE_URL = "<cadena de Neon>"
alembic downgrade base
alembic upgrade head
python -m scripts.seed
```

Esto borra todos los datos de Neon y vuelve a cargar los datos demo.
