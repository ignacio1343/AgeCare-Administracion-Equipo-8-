# Avisos de salud por WhatsApp al familiar (v0.5.1)

Cuando un paciente tiene un evento de salud de riesgo, la consola avisa por WhatsApp a sus familiares del círculo de
cuidado. Corresponde a las tablas `MENSAJE_WHATSAPP` y `REPRESENTANTE.whatsapp_habilitado` del MER original y a la
mejora propuesta en el Informe de la Entrega 2.

## Qué dispara un aviso

| Evento que informa la Plataforma AgeCare | Alerta que se crea | ¿Se avisa por WhatsApp? |
|---|---|---|
| Signo vital dentro del rango verde | Ninguna | No |
| Signo vital dentro del rango amarillo | Alerta *media* | No |
| Signo vital fuera del rango amarillo (rojo) | Alerta *crítica* | **Sí** |
| Caída detectada | Alerta *crítica* | **Sí** |
| Botón SOS | Alerta *crítica* | **Sí** |

Los rangos son los del semáforo que el administrador configura en *Configuración → Umbrales de alertas* (CU05).

## A quién se avisa y cuándo no

Se crea un registro por cada miembro del círculo con rol **familiar** y membresía **activa**. El aviso se envía solo
si se cumplen todas las reglas; si no, queda **omitido** con el motivo, para que soporte pueda explicarlo:

1. El parámetro `whatsapp_activo` está en `true` (*Configuración → Parámetros*).
2. El plan del paciente incluye la funcionalidad **Avisos de salud por WhatsApp** (por defecto Platino y Proveedor;
   se cambia en *Planes y suscripciones*).
3. La cuenta del familiar está activa, tiene teléfono y **dio su consentimiento** (*Usuarios de la app → ficha →
   Avisos de salud por WhatsApp*). Cada cambio de consentimiento queda en la auditoría con el teléfono enmascarado.
4. No recibió otro aviso del mismo paciente en los últimos `whatsapp_minutos_entre_avisos` (30 por defecto).

## Envío, reintentos y estados

```
pendiente ──envío──▶ enviado ──webhook──▶ entregado ──webhook──▶ leído
    │ falla temporal: reintento a 1, 5 y 15 min
    └─ tras whatsapp_max_intentos (3) o error permanente ──▶ fallido  (botón «Reintentar» en la consola)
omitido: no se envió (sin plan, sin consentimiento, sin teléfono o agrupado)
```

- El envío ocurre en segundo plano apenas se registra la alerta; el planificador reintenta cada minuto.
- Los estados de Meta nunca hacen retroceder un aviso (un «entregado» que llega después de un «leído» se ignora).
- La consola nunca muestra el número completo: `+569 •••• 5678`.

## Modo simulado (por defecto)

`WHATSAPP_MODO=simulado` no llama a Meta. Genera un identificador `wamid.SIM…`, marca el aviso como entregado a los
30 segundos y como leído (7 de cada 10) a los 2 minutos. Los números terminados en `0000` fallan siempre, para
probar los reintentos. Es lo que usa la demo y el CI.

Para probarlo: *Avisos WhatsApp → Simular evento de salud* → paciente con plan Platino → Signo vital →
Saturación de oxígeno → 86 → **Registrar evento**.

## Pasar a WhatsApp real (Meta WhatsApp Business Cloud API)

Requisito: la API ya publicada en Render (Meta necesita una URL pública con HTTPS para el webhook).
Tiempo: unos 30 minutos más lo que Meta tarde en aprobar la plantilla (de minutos a un día).

### Paso 1 · App y número de prueba (developers.facebook.com)

1. *My Apps* → tu app → si aún no lo tiene, *Add product* → **WhatsApp** (caso de uso «Conectar con clientes por
   WhatsApp»). Meta crea un **número de prueba** y una **cuenta de WhatsApp Business**.
2. *WhatsApp → API Setup*. Anota:
   - **Phone number ID** (del número de prueba, *From*) → `WHATSAPP_PHONE_NUMBER_ID`.
   - **WhatsApp Business Account ID** → `WHATSAPP_WABA_ID`.
3. En el campo **To** → *Manage phone number list* agrega los celulares de los tres integrantes (formato
   `+56 9 …`). Cada uno recibe un código por WhatsApp para verificarlo. El número de prueba solo puede escribir a esa
   lista (hasta 5 números); si no, Meta responde el error **131030**.
4. Pulsa *Send message* en esa misma página: debe llegarte el «Hello World» de Meta. Así confirmas que la cuenta
   funciona antes de tocar la consola.

### Paso 2 · Token permanente

El token de *API Setup* es temporal (vence en horas, error **190**). Para Render crea uno permanente:

1. <https://business.facebook.com/settings> → *Users → System users* → **Add** (rol *Admin*).
2. *Assign assets*: la **app** (control total) y la **cuenta de WhatsApp** (control total).
3. **Generate new token** → elige la app, vencimiento *Never* y los permisos `whatsapp_business_messaging`,
   `whatsapp_business_management` y `business_management`. Copia el token → `WHATSAPP_TOKEN`. Meta no lo vuelve a
   mostrar.

### Paso 3 · Plantilla del aviso

*WhatsApp Manager* (business.facebook.com/wa/manage) → *Message templates* → **Create template**:

- Categoría **Utility** · Nombre `alerta_salud_familiar` · Idioma **Spanish (es)**.
- Cuerpo (copiar tal cual, con las tres variables):
  `AgeCare · Aviso de salud de {{1}}: {{2}}. Hora: {{3}}. Revisa la app AgeCare o comunícate con la cuidadora.`
- Ejemplos de las variables: `Hilda Pérez` · `saturación de oxígeno 86 % (fuera de rango)` · `24-10 22:32`.
- Envía a revisión. Mientras esté *In review* puedes probar con `WHATSAPP_PLANTILLA=hello_world` (ver paso 5).

### Paso 4 · Variables en Render

Render → `agecare-admin-api` → **Environment** → *Add environment variable* (las secretas, como *Secret*):

| Variable | Valor |
|---|---|
| `WHATSAPP_MODO` | `meta` |
| `WHATSAPP_TOKEN` | token permanente del paso 2 |
| `WHATSAPP_PHONE_NUMBER_ID` | del paso 1 |
| `WHATSAPP_WABA_ID` | del paso 1 (permite ver si la plantilla está aprobada) |
| `WHATSAPP_APP_SECRET` | *App settings → Basic → App secret* (botón *Show*) |
| `WHATSAPP_VERIFY_TOKEN` | una frase larga inventada, p. ej. `agecare-webhook-2026-xk29` |
| `WHATSAPP_PLANTILLA` | `hello_world` mientras se aprueba la propia; después `alerta_salud_familiar` |

*Save changes*: Render reinicia la API (1 a 2 minutos). No pongas estas variables en `render.yaml` ni en GitHub.

### Paso 5 · Probar desde la consola

1. Entra como admin o soporte → **Avisos WhatsApp** → **Probar conexión**. Debe mostrar el número emisor, la
   plantilla con estado `APPROVED` (o `PENDING` si aún está en revisión) y ninguna variable faltante. Si hay un
   error, la consola explica qué corregir.
2. **Usuarios de la app** → abre un familiar → *Editar* → pon **tu celular** (uno de la lista del paso 1.3), marca
   la autorización y guarda → **Enviar WhatsApp de prueba**. Con `hello_world` llega el saludo de Meta; con la
   plantilla aprobada llega el aviso de AgeCare.
3. Para la prueba completa: **Simular evento de salud** con un paciente de ese familiar (plan Platino) y saturación
   86. El aviso real llega en segundos.

### Paso 6 · Webhook (entregado y leído)

*WhatsApp → Configuration → Webhook → Edit*:

- **Callback URL:** `https://agecare-admin-api.onrender.com/api/v1/whatsapp/webhook`
- **Verify token:** el mismo `WHATSAPP_VERIFY_TOKEN`. Pulsa *Verify and save* (la API debe estar despierta: abre
  antes `/api/v1/health`).
- En *Webhook fields* → **messages** → *Subscribe*.

Desde ahí, la bitácora pasa los avisos a **Entregado** y **Leído** cuando el familiar lo recibe y lo abre. Cada
evento llega firmado (`X-Hub-Signature-256` con el App secret); si la firma no coincide, la API lo rechaza.

### Errores frecuentes

| Código | Qué significa | Solución |
|---|---|---|
| 190 | Token vencido o inválido | Token permanente (paso 2) |
| 131030 | El destinatario no está en la lista del número de prueba | Agregarlo en *API Setup → To* (paso 1.3) |
| 132001 | La plantilla no existe o no está aprobada en ese idioma | Revisar nombre e idioma `es`, o usar `hello_world` |
| 132000 | Cantidad de variables distinta a la plantilla | El cuerpo debe tener exactamente `{{1}}`, `{{2}}` y `{{3}}` |
| 131026 | El número no tiene WhatsApp | Revisar el teléfono del familiar |
| 100 | Parámetro inválido | Revisar `WHATSAPP_PHONE_NUMBER_ID` |
| 10 | Falta permiso | Token con `whatsapp_business_messaging` |
| «Firma del webhook inválida» | `WHATSAPP_APP_SECRET` no corresponde a la app | Copiar de nuevo el App secret |

**Costos:** con el número de prueba no se cobra. Con un número propio, Meta cobra por plantilla de utilidad
enviada fuera de la ventana de 24 h (varía por país).

**Para producción** (fuera del alcance del Capstone): registrar un número propio de Wellq Co, verificar la empresa en
Meta Business y pasar la app a modo *Live*.

## Integración con la Plataforma AgeCare

La plataforma informa eventos a `POST /api/v1/integracion/eventos-salud` con la cabecera `X-API-Key` (variable
`PLATAFORMA_API_KEY`; si está vacía la integración responde 503):

```json
{ "id_paciente": 7, "tipo": "vital", "signo_vital": "saturacion_o2", "valor": 86 }
{ "id_paciente": 7, "tipo": "caida" }
```

## Privacidad (Ley 19.628)

- Datos de salud solo al familiar del círculo que dio consentimiento expreso; el consentimiento se registra con
  fecha y se puede retirar en cualquier momento.
- El mensaje contiene lo mínimo: nombre del paciente, evento, hora. El valor medido se puede quitar con el parámetro
  `whatsapp_incluir_valor = false`.
- Los registros técnicos y la auditoría guardan el teléfono enmascarado.

## Pruebas

`backend/tests/test_whatsapp.py`: 29 pruebas que cubren el semáforo, a quién se avisa, cada motivo de omisión, la
agrupación, los reintentos y el fallido, el reintento manual, el formato exacto de la plantilla de Meta, el manejo de
errores 4xx de Meta, el webhook (verificación, firma, estados que no retroceden), el consentimiento en la auditoría,
los permisos, la integración con clave, el diagnóstico con Meta y el mensaje de prueba (incluido `hello_world`).
