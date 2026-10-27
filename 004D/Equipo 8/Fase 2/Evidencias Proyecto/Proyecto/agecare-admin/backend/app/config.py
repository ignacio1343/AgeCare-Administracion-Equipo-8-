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

    # Planificador de tareas en segundo plano (0 = desactivado; los tests lo desactivan)
    planificador_intervalo_seg: int = 60
    zona_horaria: str = "America/Santiago"
    log_level: str = "INFO"  # registros técnicos (Render los muestra en la pestaña Logs)  # fechas de negocio (vigencias, métricas diarias)

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
