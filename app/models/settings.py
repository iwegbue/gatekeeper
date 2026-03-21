"""
Application settings model — singleton pattern for runtime configuration.
BYOK-focused: users configure their own AI provider keys from the UI.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Settings(Base):
    __tablename__ = "settings"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # AI Provider (BYOK)
    ai_provider: Mapped[str] = mapped_column(String(20), default="anthropic")  # anthropic, openai, ollama
    anthropic_api_key: Mapped[str] = mapped_column(String, default="")
    openai_api_key: Mapped[str] = mapped_column(String, default="")
    ollama_base_url: Mapped[str] = mapped_column(String, default="")
    ai_model: Mapped[str] = mapped_column(String(100), default="")  # e.g. "claude-sonnet-4-20250514", "gpt-4o"

    # Notifications
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    # Entry window default (hours)
    entry_window_hours: Mapped[int] = mapped_column(Integer, default=4)

    # API token (hashed)
    api_token_hash: Mapped[str | None] = mapped_column(String, nullable=True)

    # Admin password (scrypt hash — set via /setup wizard or ADMIN_PASSWORD env var at boot)
    admin_password_hash: Mapped[str | None] = mapped_column(String, nullable=True)

    # Onboarding walkthrough completed flag
    setup_completed: Mapped[bool] = mapped_column(Boolean, default=False)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), onupdate=lambda: datetime.now(timezone.utc),
    )
