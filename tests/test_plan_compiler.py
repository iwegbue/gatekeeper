"""
Tests for validation/plan_compiler.py.

Covers: compile_plan, coherence checks, interpretability score,
confirm_compiled_rule, list/get runs.
"""
import json

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import InterpretationStatus, ValidationMode, ValidationRunStatus
from app.services.validation import plan_compiler
from tests.factories import create_plan, create_rule


class MockProvider:
    """Returns a canned TESTABLE sma_trend response for any non-BEHAVIORAL rule."""

    def __init__(self, response_override: str | None = None):
        self._override = response_override
        self.model = "mock"
        self.call_count = 0

    async def chat(self, system: str, messages: list[dict]) -> str:
        self.call_count += 1
        if self._override:
            return self._override
        return json.dumps({
            "status": "TESTABLE",
            "proxy_type": "sma_trend",
            "proxy_params": {"period": 200, "timeframe": "1d", "direction_match": True},
            "confidence": 0.9,
            "interpretation_notes": "Mapped to 200 SMA trend.",
        })


# ── compile_plan ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_compile_plan_creates_compiled_plan(db: AsyncSession):
    plan = await create_plan(db)
    await create_rule(db, plan.id, layer="CONTEXT", name="Trend rule")
    provider = MockProvider()

    compiled, run = await plan_compiler.compile_plan(db, provider)

    assert compiled.plan_id == plan.id
    assert len(compiled.compiled_rules) == 1
    assert compiled.interpretability_score == 100.0


@pytest.mark.asyncio
async def test_compile_plan_creates_validation_run(db: AsyncSession):
    plan = await create_plan(db)
    await create_rule(db, plan.id, layer="CONTEXT", name="Rule")
    provider = MockProvider()

    compiled, run = await plan_compiler.compile_plan(db, provider)

    assert run.compiled_plan_id == compiled.id
    assert run.status == ValidationRunStatus.COMPLETED.value
    assert run.mode == ValidationMode.INTERPRETABILITY.value
    assert run.started_at is not None
    assert run.completed_at is not None


@pytest.mark.asyncio
async def test_compile_plan_freezes_plan_snapshot(db: AsyncSession):
    plan = await create_plan(db, name="Snapshot Plan")
    await create_rule(db, plan.id, layer="CONTEXT", name="Snapshot Rule")
    provider = MockProvider()

    compiled, _ = await plan_compiler.compile_plan(db, provider)

    assert compiled.plan_snapshot["plan_name"] == "Snapshot Plan"
    assert len(compiled.plan_snapshot["rules"]) == 1
    assert compiled.plan_snapshot["rules"][0]["name"] == "Snapshot Rule"


@pytest.mark.asyncio
async def test_compile_plan_behavioral_rules_not_sent_to_ai(db: AsyncSession):
    plan = await create_plan(db)
    await create_rule(db, plan.id, layer="CONTEXT", name="Context rule")
    await create_rule(db, plan.id, layer="BEHAVIORAL", name="No revenge trading")
    provider = MockProvider()

    await plan_compiler.compile_plan(db, provider)

    # Only 1 AI call — BEHAVIORAL is auto-classified
    assert provider.call_count == 1


@pytest.mark.asyncio
async def test_compile_plan_empty_plan_returns_perfect_score(db: AsyncSession):
    await create_plan(db)
    provider = MockProvider()

    compiled, _ = await plan_compiler.compile_plan(db, provider)

    assert compiled.compiled_rules == []
    assert compiled.interpretability_score == 100.0


# ── Interpretability score ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_interpretability_score_partial(db: AsyncSession):
    plan = await create_plan(db)
    await create_rule(db, plan.id, layer="CONTEXT", name="Testable rule")
    await create_rule(db, plan.id, layer="SETUP", name="Non-testable rule")

    not_testable_response = json.dumps({
        "status": "NOT_TESTABLE",
        "proxy_type": "not_testable",
        "proxy_params": {},
        "confidence": 0.1,
        "interpretation_notes": "Cannot interpret.",
    })

    call_count = 0

    class AlternatingProvider:
        model = "mock"

        async def chat(self, system, messages):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return json.dumps({
                    "status": "TESTABLE",
                    "proxy_type": "sma_trend",
                    "proxy_params": {"period": 200, "timeframe": "1d", "direction_match": True},
                    "confidence": 0.9,
                    "interpretation_notes": "ok",
                })
            return not_testable_response

    compiled, _ = await plan_compiler.compile_plan(db, AlternatingProvider())
    assert compiled.interpretability_score == 50.0


# ── Coherence checks ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_coherence_gap_warning_for_empty_layer(db: AsyncSession):
    plan = await create_plan(db)
    # Only CONTEXT has rules — other layers empty
    await create_rule(db, plan.id, layer="CONTEXT", name="Trend")
    provider = MockProvider()

    compiled, _ = await plan_compiler.compile_plan(db, provider)

    warnings = compiled.coherence_warnings
    gap_warnings = [w for w in warnings if "no testable required" in w.lower()]
    assert len(gap_warnings) > 0


@pytest.mark.asyncio
async def test_coherence_underfiltering_warning_few_layers(db: AsyncSession):
    plan = await create_plan(db)
    await create_rule(db, plan.id, layer="CONTEXT", name="Only rule")
    provider = MockProvider()

    compiled, _ = await plan_compiler.compile_plan(db, provider)

    warnings = " ".join(compiled.coherence_warnings).lower()
    assert "underspecified" in warnings or "fewer" in warnings or "only" in warnings


@pytest.mark.asyncio
async def test_coherence_no_warnings_when_risk_present(db: AsyncSession):
    """When all key layers have testable rules, no risk/entry warnings."""
    plan = await create_plan(db)
    await create_rule(db, plan.id, layer="RISK", name="ATR stop")
    await create_rule(db, plan.id, layer="ENTRY", name="Market entry")
    provider = MockProvider()

    compiled, _ = await plan_compiler.compile_plan(db, provider)

    no_risk_warnings = [w for w in compiled.coherence_warnings if "RISK" in w and "no testable" in w.lower()]
    assert no_risk_warnings == []


# ── confirm_compiled_rule ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_confirm_rule_marks_user_confirmed(db: AsyncSession):
    plan = await create_plan(db)
    rule = await create_rule(db, plan.id, layer="CONTEXT", name="Rule to confirm")
    provider = MockProvider()

    compiled, _ = await plan_compiler.compile_plan(db, provider)
    rule_id = str(rule.id)

    updated = await plan_compiler.confirm_compiled_rule(
        db,
        compiled.id,
        rule_id,
        status=InterpretationStatus.TESTABLE.value,
        interpretation_notes="I confirmed this.",
    )

    confirmed = next((r for r in updated.compiled_rules if r["rule_id"] == rule_id), None)
    assert confirmed is not None
    assert confirmed["user_confirmed"] is True
    assert confirmed["interpretation_notes"] == "I confirmed this."


@pytest.mark.asyncio
async def test_confirm_rule_updates_proxy(db: AsyncSession):
    plan = await create_plan(db)
    rule = await create_rule(db, plan.id, layer="CONTEXT", name="Rule")
    provider = MockProvider()

    compiled, _ = await plan_compiler.compile_plan(db, provider)

    updated = await plan_compiler.confirm_compiled_rule(
        db,
        compiled.id,
        str(rule.id),
        proxy_type="ema_trend",
        proxy_params={"period": 50, "timeframe": "4h", "direction_match": True},
    )

    rule_data = next((r for r in updated.compiled_rules if r["rule_id"] == str(rule.id)), None)
    assert rule_data["proxy"]["type"] == "ema_trend"
    assert rule_data["proxy"]["params"]["period"] == 50


@pytest.mark.asyncio
async def test_confirm_rule_returns_none_for_missing_plan(db: AsyncSession):
    import uuid
    result = await plan_compiler.confirm_compiled_rule(
        db, uuid.uuid4(), "some-rule-id", status="TESTABLE"
    )
    assert result is None


@pytest.mark.asyncio
async def test_confirm_rule_returns_none_for_missing_rule_id(db: AsyncSession):
    """confirm_compiled_rule should return None when rule_id is not in compiled_rules."""
    plan = await create_plan(db)
    await create_rule(db, plan.id, layer="CONTEXT", name="Actual rule")
    provider = MockProvider()

    compiled, _ = await plan_compiler.compile_plan(db, provider)

    result = await plan_compiler.confirm_compiled_rule(
        db, compiled.id, "non-existent-rule-id", status="TESTABLE"
    )
    assert result is None


# ── list/get runs ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_validation_runs_empty(db: AsyncSession):
    runs = await plan_compiler.list_validation_runs(db)
    assert runs == []


@pytest.mark.asyncio
async def test_list_validation_runs_returns_all_runs(db: AsyncSession):
    plan = await create_plan(db)
    await create_rule(db, plan.id, layer="CONTEXT", name="Rule")
    provider = MockProvider()

    _, run1 = await plan_compiler.compile_plan(db, provider)
    _, run2 = await plan_compiler.compile_plan(db, provider)

    runs = await plan_compiler.list_validation_runs(db)
    assert len(runs) == 2
    run_ids = {r.id for r in runs}
    assert run1.id in run_ids
    assert run2.id in run_ids


@pytest.mark.asyncio
async def test_get_validation_run_returns_none_for_missing(db: AsyncSession):
    import uuid
    run = await plan_compiler.get_validation_run(db, uuid.uuid4())
    assert run is None


@pytest.mark.asyncio
async def test_get_validation_run_returns_run(db: AsyncSession):
    plan = await create_plan(db)
    await create_rule(db, plan.id, layer="CONTEXT", name="Rule")
    provider = MockProvider()

    _, created_run = await plan_compiler.compile_plan(db, provider)
    fetched = await plan_compiler.get_validation_run(db, created_run.id)

    assert fetched is not None
    assert fetched.id == created_run.id
