"""Pydantic schemas for the Plan Review API."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RulePerformanceItem(BaseModel):
    rule_name: str
    layer: str
    adherence_pct: float
    win_rate_when_followed: float | None
    win_rate_when_skipped: float | None
    verdict: str  # keep | review | remove
    notes: str


class PlanReviewReport(BaseModel):
    summary: str
    sample_size: int
    win_rate: float
    avg_r: float | None
    rule_performance: list[RulePerformanceItem]
    assumptions_held: list[str]
    assumptions_challenged: list[str]
    suggested_changes: list[str]
    overall_verdict: str  # keep | refine | overhaul


class PlanReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    plan_id: uuid.UUID
    trade_window_start: datetime
    trade_window_end: datetime
    trade_count: int
    status: str
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class PlanReviewDetailResponse(PlanReviewResponse):
    report: dict | None = None
