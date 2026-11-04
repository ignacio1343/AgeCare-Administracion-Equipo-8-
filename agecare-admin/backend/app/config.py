"""Configuración de la API, leída desde variables de entorno o archivo .env."""
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Base de datos (PostgreSQL). Para pruebas rápidas también acepta sqlite:///archivo.db
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/agecare_admin"

    # JWT
    jwt_secret: str = "cambia-esta-clave-en-produccion-por-una-larga-y-aleatoria"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_hours: int = 12

    # Cookie del refresh token: HttpOnly (JavaScript no la puede leer, protege contra XSS).
    # Strict sirve cuando la consola y la API comparten origen (Docker: nginx; Render: rewrite /api/* del sitio estático).
    # Si se publican en dominios distintos, usar COOKIE_SAMESITE=none (exige HTTPS).
    cookie_secure: bool = True
    cookie_samesite: str = "strict"

    # Seguridad de login (spec 3.1)
    max_login_attempts: int = 5
    login_window_minutes: int = 10
    lockout_minutes: int = 15

    # Cuentas de staff
    allowed_email_domains: str = "wellq.co.uk,agecare.cl"
    activation_hours: int = 24
    frontend_url: str = "http://localhost:5173"

    # CORS
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Pasarela de pago (simulada): secreto compartido para firmar los webhooks
    pasarela_webhook_secret: str = "secreto-webhook-demo"

    # Avisos de salud por WhatsApp al familiar (WhatsApp Business Cloud API de Meta). Ver docs/WHATSAPP.md
    whatsapp_modo: str = "simulado"            # simulado | meta
    whatsapp_token: str = ""                   # token de acceso permanente (usuario del sistema en Meta Business)
    whatsapp_phone_number_id: str = ""         # id del número emisor en WhatsApp Manager
    whatsapp_api_version: str = "v22.0"
    whatsapp_plantilla: str = "alerta_salud_familiar"  # plantilla de categoría «utilidad» aprobada por Meta
    whatsapp_idioma: str = "es"
    whatsapp_app_secret: str = ""              # secreto de la app de Meta: valida la firma X-Hub-Signature-256
    whatsapp_verify_token: str = ""            # token que Meta envía al registrar el webhook
    whatsapp_waba_id: str = ""                 # id de la cuenta de WhatsApp Business (para revisar la plantilla)
    # Clave con la que la Plataforma AgeCare informa eventos de salud (vacía = integración desactivada)
    plataforma_api_key: str = ""

    # Portal web (representante, residente y cuidador) · ver docs/PORTAL.md
    # Código por correo al registrarse: «brevo» (correo real por la API HTTPS de Brevo; Render gratis bloquea SMTP)
    # o «simulado» (solo local y pruebas: el código se muestra en pantalla)
    correo_modo: str = "simulado"
    brevo_api_key: str = ""
    correo_remitente: str = ""                 # correo verificado como remitente en Brevo (p. ej. el Gmail del equipo)
    correo_remitente_nombre: str = "AgeCare"
    # Pasarela de pago del portal: «simulado» (página de pago de prueba propia) o «webpay» (Transbank Webpay Plus)
    pagos_modo: str = "simulado"
    webpay_entorno: str = "integracion"        # integracion (tarjetas de prueba) | produccion
    # Credenciales públicas del ambiente de integración de Transbank (las publica Transbank para pruebas)
    webpay_codigo_comercio: str = "597055555532"
    webpay_api_key: str = "579B532A7440BB0C9079DED94D31EA1615BACEB56610332264630D42D0A36B1C"
    # URL pública de la API (Webpay vuelve aquí tras el pago). Vacía = FRONTEND_URL (rewrite /api/* del sitio)
    api_public_url: str = ""

    # Planificador de tareas en segundo plano (0 = desactivado; los tests lo desactivan)
    planificador_intervalo_seg: int = 60
    zona_horaria: str = "America/Santiago"
    log_level: str = "INFO"  # registros técnicos (Render los muestra en la pestaña Logs)

    @field_validator("whatsapp_modo", "whatsapp_token", "whatsapp_phone_number_id", "whatsapp_api_version",
                     "whatsapp_plantilla", "whatsapp_idioma", "whatsapp_app_secret", "whatsapp_verify_token",
                     "whatsapp_waba_id", "plataforma_api_key", "correo_modo", "brevo_api_key",
                     "correo_remitente", "pagos_modo", "webpay_entorno", "webpay_codigo_comercio",
                     "webpay_api_key", "api_public_url")
    @classmethod
    def _sin_espacios(cls, v: str) -> str:
        """Al pegar claves en el panel de Render suelen colarse espacios o saltos de línea: se eliminan."""
        return "".join(v.split()) if isinstance(v, str) else v

    @field_validator("database_url")
    @classmethod
    def _driver_psycopg(cls, v: str) -> str:
        """Neon y Render entregan URLs postgres:// o postgresql://; SQLAlchemy necesita el driver psycopg 3."""
        for pref in ("postgres://", "postgresql://"):
            if v.startswith(pref):
                return "postgresql+psycopg://" + v[len(pref):]
        return v

    # Nombre que muestra la app TOTP
    totp_issuer: str = "AgeCare Admin"

    @property
    def allowed_domains(self) -> list[str]:
        return [d.strip().lower() for d in self.allowed_email_domains.split(",") if d.strip()]

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
