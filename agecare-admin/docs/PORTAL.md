# Portal web de familias (v0.7.0)

Sitio web responsivo (computador y celular) en **`/portal`** del mismo dominio de la consola:
<https://agecare-admin.onrender.com/portal>. Tiene tres vistas según el perfil de la cuenta. Una persona con más de
un perfil, por ejemplo representante y cuidadora, cambia de vista desde la cabecera.

| Vista | Perfil en la app | Qué hace |
|---|---|---|
| **Representante** | `familiar` | Se registra solo (con código por correo), contrata y paga el plan de cada residente en Webpay, lo registra, cambia, renueva o cancela su plan, ve su **estado vital en tiempo real** (Platino y Proveedor) y recibe los **avisos de riesgo** en el portal y por WhatsApp (Dorado, Platino y Proveedor). |
| **Residente** | `adulto_mayor` | Entra con su **correo o RUT**. Ve los **chistes, noticias y eventos** que publica el equipo en la consola y pide ayuda. No paga ni cambia planes. |
| **Cuidador** | `cuidadora` | Registra la **ficha vital** de sus residentes asignados (**Normal / Alerta / Riesgoso** con una observación). Queda guardado quién y cuándo. |

## De dónde llegan los tickets de los usuarios

Todos llegan a **Soporte (tickets)** de la consola con canal **App**:

| Origen en el portal | Categoría | Prioridad |
|---|---|---|
| «¿Olvidaste tu contraseña?» (pantalla de ingreso) | Acceso y cuenta | Alta |
| «Pedir ayuda» (cualquier vista) | La que elige el usuario | Media |

Para que no se pueda averiguar qué correos existen, **«¿Olvidaste tu contraseña?» responde siempre lo mismo**. Solo
crea el ticket si la cuenta existe, y como máximo uno cada 24 horas por cuenta. Soporte lo resuelve así:
**Usuarios de la app** → ficha → *Motivo* (p. ej. «Ticket #1047, identidad validada por teléfono») →
**Restablecer contraseña**. La consola muestra una **clave temporal** una sola vez. El portal obliga a cambiarla al
entrar y se cierran las sesiones anteriores.

## Cómo ve el usuario la respuesta de soporte («Mis solicitudes», CU57)

Cuando soporte responde un ticket desde la consola, el usuario lo ve en el portal:

| Qué hace soporte en la consola | Qué recibe el usuario |
|---|---|
| **Enviar respuesta** (sin marcar «Nota interna») | Aviso en la **campana** («Soporte respondió la solicitud #1050») y un **correo** con el texto de la respuesta y el botón «Ver mi solicitud» |
| Cambia el estado a **Esperando usuario** | Aviso «Soporte necesita tu respuesta» en la campana y por correo |
| Cambia el estado a **Resuelto** | Aviso «Soporte resolvió» y la **encuesta de satisfacción** (1 a 5 estrellas y comentario) en la solicitud |
| Escribe una **nota interna** | Nada: las notas internas nunca se muestran en el portal |

En **📨 Mis solicitudes** (ícono de la cabecera o enlace del pie de página):

- Cada persona ve **sus** solicitudes, con número, estado (Recibida, En atención, Espera tu respuesta, Resuelta,
  Cerrada) y la **conversación** con soporte.
- El **representante** ve además las solicitudes de **sus residentes**, marcadas «Solicitud de Rosa…», y puede
  responder por ellos. En la consola su mensaje aparece como «Carolina … (representante)».
- El usuario puede **responder**. Si la solicitud estaba *Resuelta* o *Esperando usuario*, vuelve a *En curso* en la
  cola de soporte. Una solicitud *Cerrada* no admite más mensajes.
- La **encuesta** se responde una sola vez y alimenta el indicador CSAT de soporte.
- El correo de aviso llega **solo a quien hizo la solicitud**. Al representante del residente le llega el aviso en la
  campana. Si el envío del correo falla, el aviso del portal igual queda guardado.

La demo trae el ticket «Quiero inscribirme en el bingo» de Rosa ya respondido y resuelto, con la encuesta pendiente.
Para verlo, entra al portal como `residente@agecare.cl` o `representante@agecare.cl`.

## Flujo del representante

```
Registro (correo, RUT, nombres y apellidos, teléfono con país, contraseña ×2, términos)
   │  ¿RUT o correo ya registrados? → «Inicia sesión o usa ¿Olvidaste tu contraseña?»
   ▼
Código de 6 dígitos al correo (3 intentos, reenvío cada 60 s, máx. 3 envíos, vence en 10 min)
   ▼
Elige el plan → paga en Webpay Plus (o «Activar» si es Gratuito)
   ▼
Pago aprobado → registra al residente (RUT, primer nombre, primer y segundo apellido, correo,
               fecha de nacimiento y contraseña ×2) → el residente ya puede entrar al portal
   ▼
Mis residentes: plan, pagado hasta, último estado, «Ver estado en tiempo real», «Cambiar plan»,
               «Pagar mes», «Cancelar plan», «Contratar de nuevo», «＋ Agregar residente»
```

- **RUT**: se valida el dígito verificador (módulo 11) en el navegador y en la API. Se guarda normalizado
  (`12345678-5`) y se muestra con puntos.
- **Un plan por residente**: cada residente tiene su propia suscripción. Un representante puede tener varios residentes.
- **Pago mensual**: Webpay Plus cobra una vez por transacción. Se paga el primer mes al contratar y luego con el botón
  **«Pagar mes»** (30 días más desde el fin del periodo). El cobro automático mes a mes (Webpay Oneclick) queda como
  trabajo futuro.
- **Cambiar plan**: a un plan pagado pasa por Webpay y empieza un periodo nuevo de 30 días. A Gratuito es inmediato.
- **Tiempo real**: la pantalla del residente se actualiza sola cada 15 segundos («En vivo»). La campana de avisos se
  revisa cada 30 segundos.
- **Ley 19.628**: al registrarse se guarda la fecha y la versión de los términos aceptados. El consentimiento para
  WhatsApp es opcional y se puede retirar desde el portal o desde la consola; ambos cambios quedan en la auditoría.

## Qué incluye cada plan

| | Gratuito | Dorado | Platino | Proveedor |
|---|:-:|:-:|:-:|:-:|
| Chistes, noticias y eventos para el residente · ayuda | ✔ | ✔ | ✔ | ✔ |
| Aviso de **Riesgoso** por WhatsApp y en el portal | | ✔ | ✔ | ✔ |
| **Estado vital en tiempo real** (observación, cuidador y hora) | | | ✔ | ✔ |

Las funcionalidades `alertas_whatsapp` y `estado_tiempo_real` se pueden cambiar en *Planes y suscripciones → Planes*.

## Ficha del cuidador y avisos

| Estado que registra el cuidador | Qué pasa |
|---|---|
| Normal | Solo se guarda en la ficha. |
| Alerta | Se guarda y queda una alerta *media* en la consola (Estado operativo). |
| **Riesgoso** | Alerta *crítica* + **WhatsApp** a cada representante con consentimiento (plantilla `alerta_salud_familiar`) + **aviso en su portal** (banner rojo y campana), si el plan lo incluye. Si no, el cuidador ve «El plan no incluye avisos automáticos: llama a su representante». |

Las reglas de WhatsApp son las de [`WHATSAPP.md`](WHATSAPP.md): agrupación cada 30 min, reintentos y bitácora en
*Avisos WhatsApp*. Los eventos que informa la Plataforma AgeCare (signo vital en rojo, caída o SOS) también generan el
aviso en el portal.

## Pasarela de pago: Webpay Plus (Transbank)

`PAGOS_MODO=webpay` (en `render.yaml`) usa la API REST v1.2 de Webpay Plus en el **entorno de integración**, con las
credenciales públicas de prueba de Transbank (código de comercio `597055555532`). No hay que crear cuentas.

1. El portal pide a la API crear la transacción (`POST /portal/representante/pagos`). La API llama a Transbank y
   recibe un token.
2. El navegador envía un formulario POST con `token_ws` a Webpay. La política CSP del sitio permite `form-action` a
   `webpay3gint.transbank.cl` y `webpay3g.transbank.cl`.
3. Webpay vuelve a `https://agecare-admin-api.onrender.com/api/v1/portal/pagos/webpay/retorno` (`API_PUBLIC_URL`).
   La API confirma el pago (*commit*) y solo lo acepta si `response_code = 0`, `status = AUTHORIZED` y la orden y el
   monto coinciden. Luego redirige al comprobante en `/portal/pago/resultado`.
4. Si el usuario anula (`TBK_TOKEN`) o se agota el tiempo, la orden queda **anulada**. El planificador anula las
   órdenes sin respuesta después de 30 minutos.

**Tarjetas de prueba (integración):**

| Tarjeta | Número | Resultado |
|---|---|---|
| VISA crédito | 4051 8856 0044 6623 · CVV 123 · cualquier fecha futura | Aprobada |
| Mastercard crédito | 5186 0595 5959 0568 · CVV 123 | Rechazada |
| Redcompra débito | 4051 8842 3993 7763 | Aprobada |

En la autenticación del banco simulado usa **RUT 11.111.111-1** y clave **123**.

Los pagos se ven en la consola en *Planes y suscripciones → Pagos del portal (Webpay)*. Los aprobados también
aparecen en *Transacciones*.

**Modo simulado** (`PAGOS_MODO=simulado`, el que usan el CI y el entorno local): una página de pago propia con los
botones «Pagar» y «Simular pago rechazado». Sigue el mismo camino de código que Webpay.

**Para producción** (fuera del Capstone): afiliación de Wellq Co con Transbank, código de comercio y llave propios
(`WEBPAY_ENTORNO=produccion`, `WEBPAY_CODIGO_COMERCIO`, `WEBPAY_API_KEY` como secretos en Render) y el proceso de
validación de Transbank.

## Código del registro por correo

Al registrarse, el representante recibe un **código de 6 dígitos en su correo**. Es un correo real, enviado desde el
**Gmail del equipo**, y le llega a cualquier dirección. La API genera el código y guarda solo su hash.

**Cómo se envía:** el plan gratuito de Render bloquea SMTP, así que la API no puede conectarse directo a Gmail. Por eso
llama por HTTPS a un **Google Apps Script** publicado en la cuenta Gmail del equipo, y el script envía el correo con
`MailApp`. Es gratis, no necesita registrarse en otro servicio y una cuenta Gmail permite unos 100 destinatarios al día.

**Configuración (10 minutos, una vez, con la cuenta Gmail del equipo):**

1. Entra a <https://script.google.com> con el Gmail del equipo → **Nuevo proyecto**. Ponle de nombre `AgeCare correo`.
2. Borra lo que trae el editor y pega todo el archivo [`apps_script_correo.gs`](apps_script_correo.gs).
3. En la línea `const CLAVE = '…'`, reemplaza el texto entre comillas por una **frase larga inventada**, solo con
   letras, números y guiones. Ejemplo: `agecare-correo-k39x7q2m`. Guarda con el ícono 💾.
4. **Prueba**: arriba, en la lista de funciones, elige **probar** → **Ejecutar**. Google pide permisos:
   - Elige tu cuenta.
   - Si aparece «Google no verificó esta app», ve a **Configuración avanzada** → **Ir a AgeCare correo (no seguro)**
     → **Permitir**. Es tu propio script.
   - Te llega un correo «123456 es tu código de AgeCare (prueba)».
5. **Implementar** (arriba a la derecha) → **Nueva implementación** → ícono ⚙ → **Aplicación web**:
   - Descripción: `AgeCare v1`.
   - Ejecutar como: **Yo (tu correo)**.
   - Quién tiene acceso: **Cualquier usuario**.
   - **Implementar** y copia la **URL de la aplicación web**, que termina en `/exec`.
6. En Render → `agecare-admin-api` → **Environment** → *Add environment variable*:
   - `CORREO_SCRIPT_URL` = la URL del paso 5.
   - `CORREO_SCRIPT_CLAVE` = la misma frase del paso 3 (márcala como *Secret*).
   - `CORREO_MODO=apps_script` ya viene en `render.yaml`.

   *Save changes*.

Sin la clave, el script no envía nada. No lee el correo de la cuenta: solo envía el código.

**Si después cambias el script**, usa **Implementar → Gestionar implementaciones → ✏ → Versión: Nueva versión** para
que la URL siga siendo la misma.

**Si falla**, el registro muestra el motivo:

| Mensaje | Causa | Solución |
|---|---|---|
| «faltan CORREO_SCRIPT_URL o CORREO_SCRIPT_CLAVE» | Variables sin configurar en Render | Paso 6 |
| «la clave no coincide» | La clave del script y la de Render son distintas | Cópialas iguales |
| «no respondió JSON» o «respondió 403» | La implementación no es *Aplicación web* con acceso *Cualquier usuario*, o falta autorizar | Pasos 4 y 5 |

**Alternativa:** también se puede enviar con la API de Brevo (`CORREO_MODO=brevo`, `BREVO_API_KEY` y
`CORREO_REMITENTE`) si el equipo tiene una cuenta de Brevo.

En el entorno local y en el CI (`CORREO_MODO=simulado`), el código se muestra en pantalla con el aviso «Entorno de
desarrollo».

El teléfono se sigue pidiendo en el registro, pero no se verifica: se usa para los avisos por WhatsApp.

## Cuentas desde la consola (admin y soporte)

**Usuarios de la app → ＋ Nuevo usuario**:

- **Representante**: RUT, nombres, apellidos, correo, teléfono con país y consentimiento de WhatsApp.
- **Cuidador/a**: lo mismo. Luego, en su ficha, **Residentes a cargo → Asignar**.
- **Residente**: RUT, primer nombre, apellidos, correo, fecha de nacimiento, **representante** y **plan** (asignado
  por soporte, sin cobro). Se crean su cuenta, su ficha y la suscripción en la cuenta del representante.

Cada alta entrega una **clave temporal** que se muestra una vez y se cambia al primer ingreso. Todo queda en la
auditoría. Los eventos se publican en *Contenidos y productos* con el tipo **Evento** (fecha, hora y lugar). Los eventos
pasados dejan de mostrarse en el portal al día siguiente.

## Seguridad

- Sesión propia del portal: token de tipo `app` (15 min, en memoria) y refresh rotativo en la cookie HttpOnly
  `aca_portal` (ruta `/api/v1/portal/auth`, SameSite Strict). Un token de la consola no sirve en el portal ni al
  revés. Si se reutiliza un refresh ya rotado, se revocan todas las sesiones de esa cuenta.
- Contraseñas con Argon2id. Bloqueo de 15 minutos tras 5 intentos fallidos.
- Límites contra abuso: 5 registros por teléfono y 10 por red cada hora, y 5 solicitudes de ayuda por hora.
- La verificación por correo borra el hash de la contraseña de su registro temporal al confirmarse.
- El comprobante `/portal/pago/resultado` no exige sesión, porque Webpay vuelve desde otro sitio. El número de orden es
  aleatorio (64 bits) y solo muestra el resultado y los últimos 4 dígitos de la tarjeta.

## Cuentas demo del portal

| Vista | Usuario (correo o RUT) | Contraseña |
|---|---|---|
| Representante | `representante@agecare.cl` · `16.543.210-K` | `Portal123!` |
| Residente (Platino) | `residente@agecare.cl` · `4.876.543-2` | `Residente123!` |
| Residente (Dorado) | `residente2@agecare.cl` · `5.123.456-1` | `Residente123!` |
| Cuidador | `cuidador@agecare.cl` · `17.654.321-3` | `Cuidador123!` |

Cada residente tiene su suscripción en la cuenta de su representante, con el mismo nombre y RUT que aparecen en
*Usuarios de la app*: así *Planes y suscripciones* muestra a las mismas personas que la app. La familia demo (Carolina con Rosa en Platino y Manuel en Dorado) tiene historial de la ficha vital, tres eventos
publicados y dos tickets que llegaron desde el portal. Para la demo en vivo: entra como **cuidador**, marca a Rosa como
**Riesgoso** y, en otra ventana, como **representante**. El aviso aparece en segundos y, si el teléfono de Carolina es
uno de la lista de Meta, también llega el WhatsApp.

## Endpoints

| Método y ruta (`/api/v1/portal`) | Para qué |
|---|---|
| `GET /paises` · `GET /legales` | Prefijos telefónicos · términos y privacidad vigentes |
| `POST /registro` · `/registro/reenviar` · `/registro/confirmar` | CU44 registro con código por correo |
| `POST /auth/login` · `/auth/refresh` · `/auth/logout` · `GET /auth/me` | CU45 sesión |
| `POST /auth/cambiar-password` · `POST /auth/olvide` | Cambio de clave · CU46 ticket de contraseña |
| `GET /planes` · `POST /representante/pagos` | CU47 contratar, CU49 cambiar o renovar |
| `GET\|POST /pagos/webpay/retorno` · `GET /pagos/{orden}` · `POST /pagos/{orden}/simulado` | Retorno de Webpay, comprobante, pasarela simulada |
| `GET /representante/residentes` · `POST /representante/suscripciones/{id}/residente` · `/cancelar` | Mis residentes · CU48 registrar residente · CU49 cancelar |
| `GET /representante/residentes/{id}/estado` · `PUT /me/whatsapp` | CU50 estado en tiempo real · consentimiento |
| `GET /notificaciones` · `POST /notificaciones/leer` | Avisos del portal |
| `GET /residente/inicio` · `GET /contenidos?tipo=` · `POST /ayuda` | CU51 contenidos · CU52 pedir ayuda |
| `GET /solicitudes` · `GET /solicitudes/{numero}` · `POST …/respuestas` · `POST …/encuesta` | CU57 Mis solicitudes · CU40 encuesta |
| `GET /cuidador/residentes` · `POST /cuidador/residentes/{id}/ficha` · `GET …/historial` | CU53 ficha vital |

Consola: `POST /usuarios` (CU54), `POST|DELETE /usuarios/{id}/residentes` (CU55),
`POST /usuarios/{id}/restablecer-password` (CU56), `GET /usuarios/residentes/opciones` y
`GET /comercial/ordenes-portal`.

## Pruebas

`backend/tests/test_portal.py` tiene 32 pruebas:

- RUT y validaciones del registro.
- Código por correo: intentos, reenvío, vencimiento, envío con el Apps Script de Gmail y con Brevo, y sus errores.
- Sesión: correo o RUT, refresh, reuso, bloqueo y separación de tokens entre consola y portal.
- Pagos simulados y Webpay: aprobado, rechazado, anulado, tiempo agotado, monto alterado y Transbank caído.
- Registro del residente, cambio, renovación y cancelación de plan.
- Ficha del cuidador con avisos según el plan.
- Contenidos y eventos, tickets de ayuda y de contraseña, restablecimiento desde la consola.
- Cuentas creadas por soporte y asignación de residentes.
