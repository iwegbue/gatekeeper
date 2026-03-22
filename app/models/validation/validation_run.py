"""
ValidationRun — top-level artifact for each validation execution.

Tracks status, settings, results, and feedback for a single run of the
validation pipeline against a compiled plan.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ValidationRun(Base):
    __tablename__ = "validation_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    compiled_plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default="INTERPRETABILITY")

    settings: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    summary_metrics: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    feedback: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Phase 2: populated when a market data snapshot is used for replay
    data_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), onupdate=lambda: datetime.now(timezone.utc)
    )
