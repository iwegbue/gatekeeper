import logging
import secrets
from pathlib import Path

from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

_SECRET_KEY_FILE = Path("/data/secret_key")


def _resolve_secret_key(env_value: str) -> str:
    """Return a stable SECRET_KEY, auto-generating and persisting one if needed.

    Priority:
      1. Explicit env var / .env value (non-default)
      2. Previously auto-generated key stored in /data/secret_key
      3. Freshly generated key (written to /data/secret_key for future restarts)

    Falls back gracefully when /data is not writable (e.g. tests without a volume).
    """
    _insecure = {"change-me-in-production", "secret", ""}
    if env_value not in _insecure:
        return env_value

    if _SECRET_KEY_FILE.exists():
        key = _SECRET_KEY_FILE.read_text().strip()
        if key:
            return key

    key = secrets.token_urlsafe(32)
    try:
        _SECRET_KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
        _SECRET_KEY_FILE.write_text(key)
        logger.info("Auto-generated SECRET_KEY written to %s", _SECRET_KEY_FILE)
    except OSError:
        logger.warning(
            "Could not persist SECRET_KEY to %s — using ephemeral key (sessions will not "
            "survive restarts). Mount a writable volume at /data to fix this.",
            _SECRET_KEY_FILE,
        )
    return key


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://gatekeeper:gatekeeper@db:5432/gatekeeper"

    # Auth — SECRET_KEY is resolved at startup; never stored or compared as plaintext
    SECRET_KEY: str = "change-me-in-production"

    # Optional: seed the admin password on first boot without going through /setup.
    # The value is hashed and stored in the DB immediately; it is never persisted in plaintext.
    ADMIN_PASSWORD: str = ""

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
        """Log a warning when running with an ephemeral secret key; never abort."""
        if self.SKIP_SECURITY_CHECKS == "1":
            return
        if self.SECRET_KEY == "change-me-in-production":
            logger.warning(
                "SECRET_KEY is still the default value. Sessions will not survive restarts. "
                "Mount a writable volume at /data or set SECRET_KEY explicitly."
            )


def _build_settings() -> Settings:
    raw = Settings()
    resolved_key = _resolve_secret_key(raw.SECRET_KEY)
    if resolved_key != raw.SECRET_KEY:
        return raw.model_copy(update={"SECRET_KEY": resolved_key})
    return raw


settings = _build_settings()
