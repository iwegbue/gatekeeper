"""
Pydantic schemas for the Plan Validation Engine API.
"""

import uuid
from datetime import date, datetime

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
    settings: dict | None = None
    summary_metrics: dict | None = None
    data_snapshot_id: uuid.UUID | None = None
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


class ReplayRequest(BaseModel):
    """Request body for triggering a historical replay."""

    symbol: str
    timeframe: str = "1d"
    start_date: date | None = None  # default: 1 year ago
    end_date: date | None = None    # default: today
    direction: str = "BOTH"


# ── Replay result schemas ─────────────────────────────────────────────────────


class SimulatedTradeResponse(BaseModel):
    """One simulated trade from the replay engine."""

    bar_index: int
    entry_date: str
    exit_date: str | None = None
    symbol: str
    direction: str
    entry_price: float
    exit_price: float | None = None
    stop_price: float
    target_price: float | None = None
    r_multiple: float | None = None
    exit_reason: str
    optional_score: float
    management_events: list[str]


class ReplaySummaryMetricsResponse(BaseModel):
    """Aggregated KPIs from a completed replay run."""

    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    profit_factor: float | None = None
    total_r: float
    avg_r: float | None = None
    max_r: float
    min_r: float
    max_consecutive_losses: int
    max_drawdown_r: float
    avg_optional_score: float
    avg_optional_score_winners: float
    avg_optional_score_losers: float
    bars_evaluated: int
    bars_with_signal: int
    signal_rate: float
    symbol: str
    timeframe: str
    start_date: str
    end_date: str
    bars_loaded: int
    fallback_stop_used: bool
    data_coverage_warning: str | None = None
    exit_reasons: dict
    management_events: dict
