import sys

from pydantic_settings import BaseSettings

_INSECURE_SECRET_KEYS = {"change-me-in-production", "secret", ""}
_INSECURE_PASSWORDS = {"admin", "password", ""}


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

    # Security: set to "1" to skip startup security checks (dev/test only)
    SKIP_SECURITY_CHECKS: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    def check_security(self) -> None:
        """Abort startup if dangerous defaults are in use (unless SKIP_SECURITY_CHECKS=1)."""
        if self.SKIP_SECURITY_CHECKS == "1":
            return
        errors = []
        if self.SECRET_KEY in _INSECURE_SECRET_KEYS:
            errors.append(
                "SECRET_KEY is insecure. Set a strong random value:\n"
                "  python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )
        if self.ADMIN_PASSWORD in _INSECURE_PASSWORDS:
            errors.append(
                "ADMIN_PASSWORD is insecure (default 'admin'). "
                "Set a strong password via environment variable."
            )
        if errors:
            print("\n[SECURITY] Refusing to start with insecure configuration:\n", file=sys.stderr)
            for e in errors:
                print(f"  • {e}\n", file=sys.stderr)
            print(
                "Set SKIP_SECURITY_CHECKS=1 to bypass (development/testing only).\n",
                file=sys.stderr,
            )
            sys.exit(1)


settings = Settings()
