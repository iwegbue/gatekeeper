"""
Tests for validation/feedback_service.py.

Pure unit tests — no DB needed.
Builds CompiledPlan-like objects directly.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.models.enums import InterpretationStatus
from app.services.validation.feedback_service import _assess_replay_readiness, build_report


def _make_compiled_rule(
    layer: str = "CONTEXT",
    rule_type: str = "REQUIRED",
    status: str = "TESTABLE",
    proxy_type: str = "sma_trend",
    user_confirmed: bool = False,
    name: str = "Rule",
) -> dict:
    return {
        "rule_id": str(uuid.uuid4()),
        "layer": layer,
        "name": name,
        "description": None,
        "rule_type": rule_type,
        "weight": 1,
        "status": status,
        "proxy": {"type": proxy_type, "params": {}} if status != InterpretationStatus.NOT_TESTABLE.value else None,
        "confidence": 0.9
        if status == InterpretationStatus.TESTABLE.value
        else 0.5
        if status == InterpretationStatus.APPROXIMATED.value
        else None,
        "interpretation_notes": "Test note.",
        "feature_dependencies": [],
        "user_confirmed": user_confirmed,
    }


def _make_compiled_plan(rules: list[dict], warnings: list[str] | None = None, score: float = 100.0):
    plan = MagicMock()
    plan.id = uuid.uuid4()
    plan.plan_id = uuid.uuid4()
    plan.compiled_rules = rules
    plan.interpretability_score = score
    plan.coherence_warnings = warnings or []
    plan.created_at = datetime.now(timezone.utc)
    return plan


# ── build_report structure ────────────────────────────────────────────────────


def test_build_report_returns_required_keys():
    plan = _make_compiled_plan([_make_compiled_rule()])
    report = build_report(plan)

    assert "interpretability_score" in report
    assert "replay_readiness" in report
    assert "summary" in report
    assert "rule_counts" in report
    assert "layer_breakdown" in report
    assert "coherence_warnings" in report
    assert "refinement_suggestions" in report


def test_build_report_rule_counts_correct():
    rules = [
        _make_compiled_rule(layer="CONTEXT", status="TESTABLE"),
        _make_compiled_rule(layer="SETUP", status="APPROXIMATED"),
        _make_compiled_rule(layer="ENTRY", status="NOT_TESTABLE"),
        _make_compiled_rule(layer="BEHAVIORAL", status="NOT_TESTABLE"),
    ]
    plan = _make_compiled_plan(rules)
    report = build_report(plan)

    assert report["rule_counts"]["total"] == 4
    assert report["rule_counts"]["testable"] == 1
    assert report["rule_counts"]["approximated"] == 1
    assert report["rule_counts"]["not_testable"] == 1
    assert report["rule_counts"]["behavioral"] == 1


def test_build_report_summary_mentions_counts():
    rules = [_make_compiled_rule(layer="CONTEXT", status="TESTABLE")]
    plan = _make_compiled_plan(rules)
    report = build_report(plan)

    assert "1" in report["summary"]
    assert "testable" in report["summary"].lower()


def test_build_report_all_layers_in_breakdown():
    plan = _make_compiled_plan([_make_compiled_rule(layer="CONTEXT")])
    report = build_report(plan)

    # Only layers with rules appear in the breakdown with rule entries
    layer_breakdown = report["layer_breakdown"]
    assert "CONTEXT" in layer_breakdown
    assert layer_breakdown["CONTEXT"]["testable"] == 1


def test_build_report_coherence_warnings_passed_through():
    warnings = ["Gap in SETUP layer.", "Plan may be underspecified."]
    plan = _make_compiled_plan([], warnings=warnings)
    report = build_report(plan)

    assert report["coherence_warnings"] == warnings


# ── replay_readiness ──────────────────────────────────────────────────────────


def test_replay_ready_when_all_non_behavioral_testable():
    rules = [
        _make_compiled_rule(layer="CONTEXT", status="TESTABLE"),
        _make_compiled_rule(layer="RISK", status="TESTABLE"),
        _make_compiled_rule(layer="BEHAVIORAL", status="NOT_TESTABLE"),
    ]
    readiness = _assess_replay_readiness(rules)
    assert readiness == "READY"


def test_replay_partial_when_some_not_testable():
    rules = [
        _make_compiled_rule(layer="CONTEXT", status="TESTABLE"),
        _make_compiled_rule(layer="RISK", status="TESTABLE"),
        _make_compiled_rule(layer="CONFIRMATION", status="NOT_TESTABLE"),
    ]
    readiness = _assess_replay_readiness(rules)
    assert readiness == "PARTIAL"


def test_replay_not_ready_when_no_testable_risk():
    rules = [
        _make_compiled_rule(layer="CONTEXT", status="TESTABLE"),
        _make_compiled_rule(layer="RISK", status="NOT_TESTABLE"),
    ]
    readiness = _assess_replay_readiness(rules)
    assert readiness == "NOT_READY"


def test_replay_not_ready_when_no_rules():
    readiness = _assess_replay_readiness([])
    assert readiness == "NOT_READY"


def test_replay_not_ready_when_no_testable_rules_at_all():
    rules = [
        _make_compiled_rule(layer="CONTEXT", status="NOT_TESTABLE"),
        _make_compiled_rule(layer="RISK", status="NOT_TESTABLE"),
    ]
    readiness = _assess_replay_readiness(rules)
    assert readiness == "NOT_READY"


# ── Suggestions ───────────────────────────────────────────────────────────────


def test_suggestions_mention_behavioral_rules():
    rules = [
        _make_compiled_rule(layer="BEHAVIORAL", status="NOT_TESTABLE", name="No FOMO"),
        _make_compiled_rule(layer="RISK", status="TESTABLE"),
    ]
    plan = _make_compiled_plan(rules)
    report = build_report(plan)

    suggestions_text = " ".join(report["refinement_suggestions"]).lower()
    assert "behavioral" in suggestions_text


def test_suggestions_mention_approximated_rules():
    rules = [
        _make_compiled_rule(layer="CONTEXT", status="APPROXIMATED", name="Fuzzy trend"),
        _make_compiled_rule(layer="RISK", status="TESTABLE"),
    ]
    plan = _make_compiled_plan(rules, score=50.0)
    report = build_report(plan)

    suggestions_text = " ".join(report["refinement_suggestions"]).lower()
    assert "approximat" in suggestions_text


def test_suggestions_include_replay_ready_message_when_ready():
    rules = [
        _make_compiled_rule(layer="CONTEXT", status="TESTABLE"),
        _make_compiled_rule(layer="RISK", status="TESTABLE"),
    ]
    plan = _make_compiled_plan(rules, score=100.0)
    report = build_report(plan)

    suggestions_text = " ".join(report["refinement_suggestions"]).lower()
    assert "ready for historical replay" in suggestions_text


def test_suggestions_warn_when_no_management_rules():
    rules = [
        _make_compiled_rule(layer="CONTEXT", status="TESTABLE"),
        _make_compiled_rule(layer="RISK", status="TESTABLE"),
    ]
    plan = _make_compiled_plan(rules, score=100.0)
    report = build_report(plan)

    suggestions_text = " ".join(report["refinement_suggestions"]).lower()
    assert "management" in suggestions_text


def test_layer_breakdown_marks_behavioral():
    rules = [_make_compiled_rule(layer="BEHAVIORAL", status="NOT_TESTABLE")]
    plan = _make_compiled_plan(rules)
    report = build_report(plan)

    assert report["layer_breakdown"]["BEHAVIORAL"]["behavioral"] is True


def test_layer_breakdown_rule_list_structure():
    rules = [_make_compiled_rule(layer="SETUP", status="APPROXIMATED", name="My setup rule")]
    plan = _make_compiled_plan(rules)
    report = build_report(plan)

    rule_entries = report["layer_breakdown"]["SETUP"]["rules"]
    assert len(rule_entries) == 1
    r = rule_entries[0]
    assert r["name"] == "My setup rule"
    assert r["status"] == "APPROXIMATED"
    assert r["proxy_type"] is not None
