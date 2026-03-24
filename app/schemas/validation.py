"""
Pydantic schemas for the Plan Validation Engine API.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

# ── Compiled rule ─────────────────────────────────────────────────────────────


class CompiledRuleResponse(BaseModel):
    rule_id: str
    layer: str
    name: str
    description: str | None = None
    rule_type: str
    weight: int
    status: str
    data_sources_required: list[str] = []
    confidence: float | None = None
    interpretation_notes: str
    user_confirmed: bool


# ── Compiled plan ─────────────────────────────────────────────────────────────


class CompiledPlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    plan_id: uuid.UUID
    interpretability_score: float
    coherence_warnings: list[str]
    compiled_rules: list[CompiledRuleResponse]
    created_at: datetime


# ── Validation run ────────────────────────────────────────────────────────────


class ValidationRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    compiled_plan_id: uuid.UUID
    status: str
    mode: str
    feedback: dict | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime


class ValidationRunDetailResponse(ValidationRunResponse):
    compiled_plan: CompiledPlanResponse


# ── Requests ──────────────────────────────────────────────────────────────────


class ConfirmCompiledRuleRequest(BaseModel):
    """User confirms or overrides an AI-proposed Phase 1 classification."""

    status: str | None = None
    data_sources_required: list[str] | None = None
    interpretation_notes: str | None = None
