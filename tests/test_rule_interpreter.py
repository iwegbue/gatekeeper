"""
Tests for validation/rule_interpreter.py.

Uses a MockProvider; no real API calls.
"""

import json

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import InterpretationStatus
from app.services.validation.rule_interpreter import (
    _parse_compiler_response,
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
    status: str = "OHLC_COMPUTABLE",
    data_sources: list | None = None,
    confidence: float = 0.9,
    notes: str = "Rule can be evaluated from OHLC data.",
) -> str:
    return json.dumps(
        {
            "status": status,
            "data_sources_required": data_sources or ["sma(200, 1d)", "price_close(1d)"],
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

    assert result["status"] == InterpretationStatus.LIVE_ONLY.value
    assert result["data_sources_required"] == []
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


# ── OHLC_COMPUTABLE path ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ohlc_computable_rule_calls_provider(db: AsyncSession):
    plan = await create_plan(db)
    rule = await create_rule(db, plan.id, layer="CONTEXT", name="Price above 200 SMA")
    provider = MockProvider(_make_ai_response())

    result = await interpret_rule(rule, provider, "ctx")

    assert provider.call_count == 1
    assert result["status"] == InterpretationStatus.OHLC_COMPUTABLE.value
    assert result["data_sources_required"] == ["sma(200, 1d)", "price_close(1d)"]
    assert result["confidence"] == 0.9


@pytest.mark.asyncio
async def test_ohlc_approximate_status_preserved(db: AsyncSession):
    plan = await create_plan(db)
    rule = await create_rule(db, plan.id, layer="SETUP", name="Near demand zone")
    provider = MockProvider(
        _make_ai_response(
            status="OHLC_APPROXIMATE",
            data_sources=["swing_high(5)", "atr(14)"],
            confidence=0.5,
            notes="Partially capturable — zone width requires approximation.",
        )
    )

    result = await interpret_rule(rule, provider, "ctx")

    assert result["status"] == InterpretationStatus.OHLC_APPROXIMATE.value
    assert result["data_sources_required"] == ["swing_high(5)", "atr(14)"]
    assert result["confidence"] == 0.5


@pytest.mark.asyncio
async def test_live_only_rule_has_no_data_sources(db: AsyncSession):
    plan = await create_plan(db)
    rule = await create_rule(db, plan.id, layer="CONFIRMATION", name="Gut feeling confirms")
    provider = MockProvider(
        _make_ai_response(
            status="LIVE_ONLY",
            data_sources=[],
            confidence=0.1,
            notes="Requires discretionary judgment; cannot be derived from OHLC.",
        )
    )

    result = await interpret_rule(rule, provider, "ctx")

    assert result["status"] == InterpretationStatus.LIVE_ONLY.value
    assert result["data_sources_required"] == []


# ── Invalid / unexpected AI responses ────────────────────────────────────────


@pytest.mark.asyncio
async def test_unknown_status_falls_back_to_live_only(db: AsyncSession):
    """If AI returns an unknown status string, rule is classified LIVE_ONLY."""
    plan = await create_plan(db)
    rule = await create_rule(db, plan.id, layer="CONTEXT", name="Some rule")
    bad_response = json.dumps(
        {
            "status": "INVENTED_STATUS",
            "data_sources_required": [],
            "confidence": 0.8,
            "interpretation_notes": "Made up status.",
        }
    )
    provider = MockProvider(bad_response)

    result = await interpret_rule(rule, provider, "ctx")

    assert result["status"] == InterpretationStatus.LIVE_ONLY.value
    assert result["data_sources_required"] == []


@pytest.mark.asyncio
async def test_live_only_status_clears_data_sources_even_if_ai_returns_them(db: AsyncSession):
    """If AI returns LIVE_ONLY but also populates data_sources_required, sources are cleared."""
    plan = await create_plan(db)
    rule = await create_rule(db, plan.id, layer="CONTEXT", name="Ambiguous rule")
    contradictory_response = json.dumps(
        {
            "status": "LIVE_ONLY",
            "data_sources_required": ["sma(200, 1d)"],
            "confidence": 0.2,
            "interpretation_notes": "Could not reliably classify.",
        }
    )
    provider = MockProvider(contradictory_response)

    result = await interpret_rule(rule, provider, "ctx")

    assert result["status"] == InterpretationStatus.LIVE_ONLY.value
    assert result["data_sources_required"] == []


@pytest.mark.asyncio
async def test_malformed_json_response_falls_back_gracefully(db: AsyncSession):
    plan = await create_plan(db)
    rule = await create_rule(db, plan.id, layer="CONTEXT", name="Rule")
    provider = MockProvider("this is not json !!!")

    result = await interpret_rule(rule, provider, "ctx")

    assert result["status"] == InterpretationStatus.LIVE_ONLY.value
    assert result["data_sources_required"] == []
    notes = result["interpretation_notes"].lower()
    assert "model" in notes and "live-only" in notes


@pytest.mark.asyncio
async def test_empty_model_response_falls_back_gracefully(db: AsyncSession):
    plan = await create_plan(db)
    rule = await create_rule(db, plan.id, layer="CONTEXT", name="Rule")
    provider = MockProvider("")

    result = await interpret_rule(rule, provider, "ctx")

    assert result["status"] == InterpretationStatus.LIVE_ONLY.value
    assert "empty" in result["interpretation_notes"].lower()


# ── JSON parsing helpers ───────────────────────────────────────────────────────


def test_parse_compiler_response_strips_markdown_json_fence():
    inner = _make_ai_response()
    raw = f"Here you go:\n```json\n{inner}\n```\n"
    parsed = _parse_compiler_response(raw)
    assert parsed["status"] == "OHLC_COMPUTABLE"
    assert "data_sources_required" in parsed


def test_parse_compiler_response_strips_generic_fence():
    inner = _make_ai_response()
    raw = f"```\n{inner}\n```"
    parsed = _parse_compiler_response(raw)
    assert parsed["status"] == "OHLC_COMPUTABLE"


def test_parse_compiler_response_tolerates_preamble_and_trailing_text():
    inner = _make_ai_response()
    raw = f"The compiled rule follows.\n{inner}\nHope this helps."
    parsed = _parse_compiler_response(raw)
    assert parsed["status"] == "OHLC_COMPUTABLE"


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
    assert behavioral["status"] == InterpretationStatus.LIVE_ONLY.value
