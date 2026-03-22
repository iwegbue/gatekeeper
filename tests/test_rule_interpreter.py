"""
Tests for validation/rule_interpreter.py.

Uses a MockProvider; no real API calls.
"""

import json

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import InterpretationStatus
from app.services.validation.rule_interpreter import (
    PROXY_VOCABULARY,
    _resolve_feature_dependencies,
    interpret_rule,
    interpret_rules,
)
from tests.factories import create_plan, create_rule


class MockProvider:
    def __init__(self, response: str = "{}"):
        self._response = response
        self.model = "mock"
        self.call_count = 0
        self.last_messages = None

    async def chat(self, system: str, messages: list[dict]) -> str:
        self.call_count += 1
        self.last_messages = messages
        return self._response


def _make_ai_response(
    status: str = "TESTABLE",
    proxy_type: str = "sma_trend",
    proxy_params: dict | None = None,
    confidence: float = 0.9,
    notes: str = "Mapped to SMA trend proxy.",
) -> str:
    return json.dumps(
        {
            "status": status,
            "proxy_type": proxy_type,
            "proxy_params": proxy_params or {"period": 200, "timeframe": "1d", "direction_match": True},
            "confidence": confidence,
            "interpretation_notes": notes,
        }
    )


# ── BEHAVIORAL auto-classification ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_behavioral_rule_classified_without_ai_call(db: AsyncSession):
    plan = await create_plan(db)
    rule = await create_rule(db, plan.id, layer="BEHAVIORAL", name="No revenge trading")
    provider = MockProvider()

    result = await interpret_rule(rule, provider, "plan context")

    assert result["status"] == InterpretationStatus.NOT_TESTABLE.value
    assert result["proxy"] is None
    assert provider.call_count == 0
    assert "live enforcement" in result["interpretation_notes"]


@pytest.mark.asyncio
async def test_behavioral_rule_preserves_rule_fields(db: AsyncSession):
    plan = await create_plan(db)
    rule = await create_rule(db, plan.id, layer="BEHAVIORAL", name="No FOMO trades", rule_type="ADVISORY", weight=2)
    provider = MockProvider()

    result = await interpret_rule(rule, provider, "ctx")

    assert result["rule_id"] == str(rule.id)
    assert result["layer"] == "BEHAVIORAL"
    assert result["name"] == "No FOMO trades"
    assert result["rule_type"] == "ADVISORY"
    assert result["weight"] == 2
    assert result["user_confirmed"] is False


# ── AI call path ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_testable_rule_calls_provider(db: AsyncSession):
    plan = await create_plan(db)
    rule = await create_rule(db, plan.id, layer="CONTEXT", name="Price above 200 SMA")
    provider = MockProvider(_make_ai_response())

    result = await interpret_rule(rule, provider, "ctx")

    assert provider.call_count == 1
    assert result["status"] == InterpretationStatus.TESTABLE.value
    assert result["proxy"] == {
        "type": "sma_trend",
        "params": {"period": 200, "timeframe": "1d", "direction_match": True},
    }
    assert result["confidence"] == 0.9


@pytest.mark.asyncio
async def test_approximated_rule_status_preserved(db: AsyncSession):
    plan = await create_plan(db)
    rule = await create_rule(db, plan.id, layer="SETUP", name="Near demand zone")
    provider = MockProvider(
        _make_ai_response(
            status="APPROXIMATED",
            proxy_type="zone_proximity",
            proxy_params={"zone_atr_multiple": 0.5},
            confidence=0.5,
        )
    )

    result = await interpret_rule(rule, provider, "ctx")

    assert result["status"] == InterpretationStatus.APPROXIMATED.value
    assert result["proxy"]["type"] == "zone_proximity"
    assert result["confidence"] == 0.5


@pytest.mark.asyncio
async def test_not_testable_rule_has_no_proxy(db: AsyncSession):
    plan = await create_plan(db)
    rule = await create_rule(db, plan.id, layer="CONFIRMATION", name="Gut feeling confirms")
    provider = MockProvider(
        _make_ai_response(
            status="NOT_TESTABLE",
            proxy_type="not_testable",
            proxy_params={},
            confidence=0.1,
            notes="Cannot be objectively measured.",
        )
    )

    result = await interpret_rule(rule, provider, "ctx")

    assert result["status"] == InterpretationStatus.NOT_TESTABLE.value
    assert result["proxy"] is None


# ── Unknown / invalid proxy type ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_not_testable_status_with_valid_proxy_type_clears_proxy(db: AsyncSession):
    """If AI returns NOT_TESTABLE status but a valid proxy_type, proxy must be cleared."""
    plan = await create_plan(db)
    rule = await create_rule(db, plan.id, layer="CONTEXT", name="Ambiguous rule")
    contradictory_response = json.dumps(
        {
            "status": "NOT_TESTABLE",
            "proxy_type": "sma_trend",
            "proxy_params": {"period": 200, "timeframe": "1d", "direction_match": True},
            "confidence": 0.2,
            "interpretation_notes": "Could not reliably classify.",
        }
    )
    provider = MockProvider(contradictory_response)

    result = await interpret_rule(rule, provider, "ctx")

    assert result["status"] == InterpretationStatus.NOT_TESTABLE.value
    assert result["proxy"] is None
    assert result["feature_dependencies"] == []


@pytest.mark.asyncio
async def test_unknown_proxy_type_clears_confidence(db: AsyncSession):
    """Confidence should be zeroed when the AI returns an unknown proxy type."""
    plan = await create_plan(db)
    rule = await create_rule(db, plan.id, layer="CONTEXT", name="Some rule")
    bad_response = json.dumps(
        {
            "status": "TESTABLE",
            "proxy_type": "invented_proxy_xyz",
            "proxy_params": {},
            "confidence": 0.8,
            "interpretation_notes": "Made up type.",
        }
    )
    provider = MockProvider(bad_response)

    result = await interpret_rule(rule, provider, "ctx")

    assert result["status"] == InterpretationStatus.NOT_TESTABLE.value
    assert result["proxy"] is None
    assert result["confidence"] == 0.0


@pytest.mark.asyncio
async def test_unknown_proxy_type_falls_back_to_not_testable(db: AsyncSession):
    plan = await create_plan(db)
    rule = await create_rule(db, plan.id, layer="CONTEXT", name="Some rule")
    bad_response = json.dumps(
        {
            "status": "TESTABLE",
            "proxy_type": "invented_proxy_xyz",
            "proxy_params": {},
            "confidence": 0.8,
            "interpretation_notes": "Made up type.",
        }
    )
    provider = MockProvider(bad_response)

    result = await interpret_rule(rule, provider, "ctx")

    assert result["status"] == InterpretationStatus.NOT_TESTABLE.value
    assert result["proxy"] is None


@pytest.mark.asyncio
async def test_malformed_json_response_falls_back_gracefully(db: AsyncSession):
    plan = await create_plan(db)
    rule = await create_rule(db, plan.id, layer="CONTEXT", name="Rule")
    provider = MockProvider("this is not json !!!")

    result = await interpret_rule(rule, provider, "ctx")

    assert result["status"] == InterpretationStatus.NOT_TESTABLE.value
    assert result["proxy"] is None
    assert "failed" in result["interpretation_notes"].lower()


# ── Feature dependencies ──────────────────────────────────────────────────────


def test_resolve_feature_dependencies_sma():
    deps = _resolve_feature_dependencies("sma_trend", {"period": 200, "timeframe": "1d"})
    assert "sma_200_1d" in deps


def test_resolve_feature_dependencies_atr():
    deps = _resolve_feature_dependencies("atr_stop", {"atr_period": 14, "atr_multiple": 1.5})
    assert "atr_14" in deps


def test_resolve_feature_dependencies_no_proxy():
    deps = _resolve_feature_dependencies("not_testable", {})
    assert deps == []


def test_resolve_feature_dependencies_unknown_type():
    deps = _resolve_feature_dependencies("nonexistent_proxy", {})
    assert deps == []


# ── Batch interpretation ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_interpret_rules_processes_all_rules(db: AsyncSession):
    plan = await create_plan(db)
    rules = [
        await create_rule(db, plan.id, layer="CONTEXT", name="Trend rule"),
        await create_rule(db, plan.id, layer="SETUP", name="Setup rule"),
        await create_rule(db, plan.id, layer="BEHAVIORAL", name="Behavioral rule"),
    ]
    provider = MockProvider(_make_ai_response())

    results = await interpret_rules(rules, provider, "ctx")

    assert len(results) == 3
    # BEHAVIORAL should not have called AI
    assert provider.call_count == 2
    behavioral = next(r for r in results if r["layer"] == "BEHAVIORAL")
    assert behavioral["status"] == InterpretationStatus.NOT_TESTABLE.value


# ── Proxy vocabulary completeness ─────────────────────────────────────────────


def test_all_proxy_types_have_required_fields():
    required_keys = {"layer", "description", "params", "feature_dependencies"}
    for proxy_type, meta in PROXY_VOCABULARY.items():
        missing = required_keys - meta.keys()
        assert not missing, f"Proxy type '{proxy_type}' missing keys: {missing}"
