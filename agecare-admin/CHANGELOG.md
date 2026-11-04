# Cambios

## v0.6.1 · 04/11/2026 · Código del registro por correo y planes con los usuarios reales

- **El código del registro llega por correo** (Brevo, API HTTPS, gratis hasta 300 al día). Reemplaza al SMS
  simulado. El plan gratuito de Render bloquea SMTP, por eso no se usa Gmail directo.
  - Se mantienen los 3 intentos, el reenvío cada 60 s y el vencimiento de 10 min.
  - Se quitó Twilio.
- Migración `0005_correo`: `verificacion_sms` pasa a llamarse `verificacion_correo`.
- **Planes y suscripciones muestran a los mismos usuarios de la app**: cada representante tiene una cuenta con su
  nombre, correo y RUT, y cada residente su suscripción.
  - Se reemplazaron, una sola vez al desplegar, las cuentas demo inventadas y las de tipo proveedor.
  - Los usuarios y pacientes demo reciben RUT y apellidos separados.

## v0.6.0 · 04/11/2026 · Portal web de familias

- **Portal responsivo en `/portal`** con tres vistas: representante, residente y cuidador.
- **Registro del representante** con correo, RUT (dígito verificador, módulo 11), nombres, primer y segundo
  apellido, teléfono con selector de país (+56, +54…) y contraseña repetida.
  - Si el RUT no tiene cuenta, se envía un **código de verificación**: 3 intentos, reenvío cada 60 s, máximo 3
    envíos y vence en 10 min (en v0.6.1 pasó de SMS a correo).
  - Se registra el consentimiento de los términos (Ley 19.628) y, opcionalmente, el de WhatsApp.
- **Pasarela de pago real: Webpay Plus de Transbank** (API REST v1.2, entorno de integración).
  - Contratar, cambiar de plan y **«Pagar mes»**.
  - El commit se valida contra el monto y la orden. Se manejan la anulación y el tiempo agotado.
  - El portal muestra un comprobante del pago.
  - En la consola: *Planes → Pagos del portal*.
- **Residente por plan**: cuando el pago se aprueba, el representante registra al residente (RUT, primer nombre,
  apellidos, correo, fecha de nacimiento y contraseña). Puede tener varios residentes y cancelar o contratar de
  nuevo el plan de cada uno.
- **Ficha vital del cuidador** (Normal / Alerta / Riesgoso con observación, cuidador y hora).
  - Riesgoso avisa por **WhatsApp** y con un **aviso en el portal** del representante (banner y campana).
  - Aplica a los planes **Dorado**, Platino y Proveedor. Dorado se agregó a `alertas_whatsapp`.
- **Estado vital en tiempo real** para Platino y Proveedor: nueva funcionalidad `estado_tiempo_real`, se actualiza
  cada 15 s.
- **Residente**: entra con correo o RUT y ve chistes, noticias y **eventos** (nuevo tipo de contenido con fecha y
  lugar).
- **Tickets desde la app**: «¿Olvidaste tu contraseña?» y «Pedir ayuda» crean tickets con canal *App*.
  Soporte restablece la clave desde la ficha del usuario con una clave temporal que el portal obliga a cambiar.
- **Consola**:
  - Admin y soporte crean representantes, cuidadores y residentes (con RUT y apellidos separados) y les asignan
    residentes.
  - Las suscripciones muestran el residente.
- Migración `0004_portal`: 5 tablas nuevas (`sesion_app`, `verificacion_sms`, `registro_vital`, `notificacion_app`,
  `orden_pago`). El esquema queda en 48 tablas. Datos demo de una familia completa.
- 116 pruebas automáticas (32 nuevas del portal), cobertura 92 %.

## v0.5.1 · 26/10/2026 · WhatsApp real con Meta

- **Probar conexión** en *Avisos WhatsApp*: comprueba con Meta el número emisor, el token, el estado de la plantilla
  (`WHATSAPP_WABA_ID`) y las variables del webhook, sin enviar mensajes.
- **Enviar WhatsApp de prueba** desde la ficha del familiar (queda en la bitácora y en la auditoría).
- Soporte para la plantilla de ejemplo `hello_world` mientras Meta aprueba `alerta_salud_familiar`.
- Los errores de Meta se muestran con su código y qué hacer (190, 131030, 132001, 132000, 131026…).
- `WHATSAPP_MODO` sale de `render.yaml`: se configura en el panel de Render junto con los secretos.
- Guía paso a paso en `docs/WHATSAPP.md`. 81 pruebas automáticas.

## v0.5.0 · 24/10/2026 · Avisos de salud por WhatsApp al familiar

- **Nuevo módulo «Avisos WhatsApp»** (CU41 registrar evento de salud, CU42 avisar al familiar, CU43 consultar avisos):
  signo vital en rojo, caída o SOS generan una alerta crítica y un aviso por WhatsApp a cada familiar del círculo de
  cuidado con consentimiento, si el plan del paciente incluye la funcionalidad (Platino y Proveedor).
- Envío con la WhatsApp Business Cloud API de Meta (plantilla aprobada) o en modo simulado; reintentos a 1, 5 y 15 min;
  webhook de estados firmado (`X-Hub-Signature-256`) que marca entregado y leído; avisos agrupados cada 30 min.
- Teléfono y consentimiento del familiar en la ficha de **Usuarios de la app**, con auditoría y teléfono enmascarado.
- Integración `POST /api/v1/integracion/eventos-salud` para la Plataforma AgeCare con clave `X-API-Key`.
- Migración `0003_whatsapp`: tabla `mensaje_whatsapp`, columnas de teléfono y consentimiento en `usuario_app` y detalle de
  la lectura en `alerta` (43 tablas). Parámetros `whatsapp_*` en Configuración. Datos demo con 51 avisos.
- 76 pruebas automáticas (24 nuevas), 91 % de cobertura. Guía en `docs/WHATSAPP.md`.

## v0.4.0 · 24/10/2026 · Sprints 5 y 6 (EP10 Plataforma, calidad y despliegue)

### Seguridad
- El refresh token pasa de `localStorage` a una cookie `HttpOnly`, `Secure` y `SameSite=Strict`, limitada a
  `/api/v1/auth`. Se agrega la cabecera anti-CSRF `X-ACA-Refresh` en `/auth/refresh` y `/auth/logout`. Ya no viaja
  en el cuerpo de las respuestas.
- Argon2id con los parámetros mínimos de OWASP (19 MiB, t=2, p=1). Los hashes anteriores se migran solos al
  iniciar sesión. Corrige **DEF-09**: login p95 de 2,7 s a 390 ms con 50 usuarios.
- Cabeceras de seguridad en la consola (CSP, `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`) en
  Render y en nginx.

### Frontend
- react-router-dom 6.30 → **react-router 7.18** (**DEF-07**) y Vite 5 → **Vite 7.3** con plugin-react 5.2
  (**DEF-08**). `npm audit`: 0 vulnerabilidades. Requiere Node 20.19 o superior.

### Observabilidad (HU06)
- Registro de una línea por petición con duración y `request_id`; los errores no controlados se registran con su
  traza. Nuevo `GET /api/v1/health/db`.
- El planificador ya no repite la traza completa cada minuto cuando la base está caída (**DEF-10**).

### Despliegue y CI/CD (HU04, HU05)
- `render.yaml`: la consola llama a la API por su mismo origen (rewrite `/api/*`), despliegue solo con el CI en
  verde (`autoDeployTrigger: checksPass`) y Node 22 en el build.
- GitHub Actions: `ci.yml` (pruebas sobre PostgreSQL, cobertura ≥ 85 %, migraciones, bandit, pip-audit, build,
  npm audit, Docker), `carga.yml` (Locust sobre la URL pública) y `zap.yml` (OWASP ZAP baseline).

### Pruebas (HU07, HU08)
- 52 pruebas automáticas (12 unitarias + 40 de integración), 90 % de cobertura.
- Locust en `tests/carga/` con `evaluar.py`, que compara contra RNF-08.

### Documentación (HU09)
- Manual de usuario de la consola y guía `docs/DESPLIEGUE_RENDER_NEON.md`.

## v0.3.0 · 09/10/2026 · Entrega 2 (Sprints 1 a 4)
- 40 casos de uso en 9 módulos, 42 tablas, 45 pruebas automáticas.
