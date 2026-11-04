/**
 * AgeCare · envío del código de registro por correo desde el Gmail del equipo.
 *
 * Cómo usarlo (detalle en docs/PORTAL.md → «Código del registro por correo»):
 *   1. https://script.google.com → Nuevo proyecto → borra todo y pega este archivo.
 *   2. Cambia CLAVE por una frase larga inventada (solo letras y números). La misma va en Render como
 *      CORREO_SCRIPT_CLAVE.
 *   3. Implementar → Nueva implementación → tipo «Aplicación web» → Ejecutar como: «Yo» →
 *      Quién tiene acceso: «Cualquier usuario» → Implementar → Autorizar acceso (elige tu cuenta →
 *      Configuración avanzada → Ir a AgeCare (no seguro) → Permitir).
 *   4. Copia la URL de la aplicación web (termina en /exec) → en Render: CORREO_SCRIPT_URL.
 *
 * Seguridad: sin la CLAVE el script no envía nada. Solo envía el correo con el código; no lee tu correo.
 * Límite de Google para cuentas Gmail gratuitas: unos 100 destinatarios al día.
 */
const CLAVE = 'CAMBIA-ESTA-CLAVE-por-una-frase-larga-2026';

function responder(datos) {
  return ContentService.createTextOutput(JSON.stringify(datos)).setMimeType(ContentService.MimeType.JSON);
}

function doPost(e) {
  try {
    const d = JSON.parse(e.postData.contents);
    if (d.clave !== CLAVE) return responder({ ok: false, error: 'clave' });
    if (!d.para || !d.asunto || !d.html) return responder({ ok: false, error: 'faltan datos' });
    MailApp.sendEmail({ to: d.para, subject: d.asunto, htmlBody: d.html, body: d.texto || '', name: d.remitente || 'AgeCare' });
    return responder({ ok: true, restantes: MailApp.getRemainingDailyQuota() });
  } catch (err) {
    return responder({ ok: false, error: String(err) });
  }
}

// Para probar desde el editor: selecciona «probar» y pulsa Ejecutar. Te llega un correo a ti mismo.
function probar() {
  MailApp.sendEmail({ to: Session.getActiveUser().getEmail(), subject: '123456 es tu código de AgeCare (prueba)',
    htmlBody: '<p>Si te llegó este correo, el script funciona.</p>', name: 'AgeCare' });
}
