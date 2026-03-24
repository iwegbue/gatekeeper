"""
PlanReview — AI-powered plan review based on a sample of real trades and journal entries.

Each review analyses the last N completed journal entries for a plan and produces
a structured report covering per-rule performance, assumptions, and suggested changes.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PlanReview(Base):
    """
    A single plan review execution record.

    report is a JSONB dict with the shape:
    {
        "summary": str,
        "sample_size": int,
        "win_rate": float,
        "avg_r": float | null,
        "rule_performance": [
            {
                "rule_name": str,
                "layer": str,
                "adherence_pct": float,
                "win_rate_when_followed": float | null,
                "win_rate_when_skipped": float | null,
                "verdict": "keep" | "review" | "remove",
                "notes": str
            }
        ],
        "assumptions_held": [str],
        "assumptions_challenged": [str],
        "suggested_changes": [str],
        "overall_verdict": "keep" | "refine" | "overhaul"
    }
    """

    __tablename__ = "plan_reviews"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)

    trade_window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    trade_window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    trade_count: Mapped[int] = mapped_column(Integer, nullable=False)

    # PENDING / COMPLETED / FAILED
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")

    report: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
