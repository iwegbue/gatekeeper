"""
CompiledPlan — the interpreted plan artifact produced by the rule compiler.

Stores a frozen snapshot of the plan at compile time plus the AI-proposed
(and user-confirmable) machine-testable proxy for each rule.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Numeric, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CompiledPlan(Base):
    """
    Frozen, interpreted representation of a TradingPlan for validation purposes.

    compiled_rules is a JSONB array. Each element has the shape:
    {
        "rule_id": str,
        "layer": str,
        "name": str,
        "description": str | null,
        "rule_type": str,
        "weight": int,
        "status": "TESTABLE" | "APPROXIMATED" | "NOT_TESTABLE",
        "proxy": {"type": str, "params": {...}} | null,
        "confidence": float | null,
        "interpretation_notes": str,
        "feature_dependencies": [str],
        "user_confirmed": bool
    }
    """
    __tablename__ = "compiled_plans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)

    plan_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    compiled_rules: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    interpretability_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0.0)
    coherence_warnings: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
