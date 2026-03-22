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
    proxy: dict | None = None
    confidence: float | None = None
    interpretation_notes: str
    feature_dependencies: list[str]
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
    """User confirms or overrides an AI-proposed interpretation."""
    status: str | None = None
    proxy_type: str | None = None
    proxy_params: dict | None = None
    interpretation_notes: str | None = None
