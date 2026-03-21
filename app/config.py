from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://gatekeeper:gatekeeper@db:5432/gatekeeper"

    # Auth
    SECRET_KEY: str = "change-me-in-production"
    ADMIN_PASSWORD: str = "admin"

    # AI (env-var fallback; primary config is in DB settings)
    ANTHROPIC_API_KEY: str = ""

    # Email notifications (SendGrid)
    SENDGRID_API_KEY: str = ""
    SENDGRID_FROM_EMAIL: str = ""
    NOTIFY_EMAIL: str = ""

    # Telegram
    TELEGRAM_BOT_TOKEN: str = ""
    APP_BASE_URL: str = "http://localhost"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
