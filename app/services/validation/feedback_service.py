"""
Feedback service — transforms a CompiledPlan into a structured,
human-readable validation report.

This is the output layer for Phase 1 (interpretability). It produces:
  - Per-layer breakdown of rule testability
  - Interpretability score summary
  - Coherence warnings
  - Replay readiness assessment
  - Actionable refinement suggestions
"""

from app.models.enums import InterpretationStatus, PlanLayer
from app.models.validation.compiled_plan import CompiledPlan

_REPLAY_READY = "READY"
_REPLAY_PARTIAL = "PARTIAL"
_REPLAY_NOT_READY = "NOT_READY"


def _layer_breakdown(compiled_rules: list[dict]) -> dict:
    """Per-layer count of rule testability statuses."""
    breakdown: dict[str, dict] = {}
    for layer in PlanLayer:
        breakdown[layer.value] = {
            "testable": 0,
            "approximated": 0,
            "not_testable": 0,
            "behavioral": layer == PlanLayer.BEHAVIORAL,
            "rules": [],
        }

    for rule in compiled_rules:
        layer = rule["layer"]
        status = rule["status"]
        if layer not in breakdown:
            breakdown[layer] = {"testable": 0, "approximated": 0, "not_testable": 0, "behavioral": False, "rules": []}

        if status == InterpretationStatus.TESTABLE.value:
            breakdown[layer]["testable"] += 1
        elif status == InterpretationStatus.APPROXIMATED.value:
            breakdown[layer]["approximated"] += 1
        else:
            breakdown[layer]["not_testable"] += 1

        breakdown[layer]["rules"].append(
            {
                "name": rule["name"],
                "rule_type": rule["rule_type"],
                "status": status,
                "proxy_type": rule["proxy"]["type"] if rule.get("proxy") else None,
                "confidence": rule.get("confidence"),
                "interpretation_notes": rule.get("interpretation_notes", ""),
                "user_confirmed": rule.get("user_confirmed", False),
            }
        )

    return breakdown


def _assess_replay_readiness(compiled_rules: list[dict]) -> str:
    """
    Determine overall replay readiness.
    READY     — all non-behavioral rules are testable or approximated.
    PARTIAL   — some rules are testable/approximated but important gaps exist.
    NOT_READY — no testable rules or critical layers (RISK) are fully non-testable.
    """
    non_behavioral = [r for r in compiled_rules if r["layer"] != PlanLayer.BEHAVIORAL.value]
    if not non_behavioral:
        return _REPLAY_NOT_READY

    testable_count = sum(
        1
        for r in non_behavioral
        if r["status"] in (InterpretationStatus.TESTABLE.value, InterpretationStatus.APPROXIMATED.value)
    )

    risk_rules = [r for r in compiled_rules if r["layer"] == PlanLayer.RISK.value]
    has_testable_risk = any(r["status"] != InterpretationStatus.NOT_TESTABLE.value for r in risk_rules)

    if testable_count == 0:
        return _REPLAY_NOT_READY
    if not has_testable_risk:
        return _REPLAY_NOT_READY
    if testable_count == len(non_behavioral):
        return _REPLAY_READY
    return _REPLAY_PARTIAL


def _generate_suggestions(
    compiled_rules: list[dict],
    layer_data: dict,
    coherence_warnings: list[str],
    interpretability_score: float,
    replay_readiness: str,
) -> list[str]:
    """Generate actionable refinement suggestions."""
    suggestions: list[str] = []

    # Score-based
    if interpretability_score < 40:
        suggestions.append(
            "More than half of your testable rules could not be interpreted. "
            "Consider adding specific, measurable criteria (e.g., 'price above 200-period SMA on the daily chart' "
            "instead of 'trade with the trend')."
        )
    elif interpretability_score < 70:
        suggestions.append(
            "Several rules required approximation. Review the interpretation notes for each approximated rule "
            "and confirm whether the proxy captures your intent."
        )

    # Layer-specific suggestions
    for layer_name, data in layer_data.items():
        if layer_name == PlanLayer.BEHAVIORAL.value:
            continue
        total = data["testable"] + data["approximated"] + data["not_testable"]
        if total > 0 and data["not_testable"] == total:
            suggestions.append(
                f"All rules in the {layer_name} layer are non-testable. "
                "Consider adding at least one objective, measurable rule to this layer."
            )

    # Risk layer suggestion
    risk_data = layer_data.get(PlanLayer.RISK.value, {})
    if risk_data.get("not_testable", 0) > 0 and risk_data.get("testable", 0) == 0:
        suggestions.append(
            "Your RISK layer has no testable stop-loss rule. "
            "Without a testable stop, replay cannot compute R-multiples. "
            "Consider adding an ATR-based or swing-based stop rule."
        )

    # Management suggestions
    mgmt_data = layer_data.get(PlanLayer.MANAGEMENT.value, {})
    mgmt_total = mgmt_data.get("testable", 0) + mgmt_data.get("approximated", 0)
    if mgmt_total == 0:
        suggestions.append(
            "No testable MANAGEMENT rules were found. "
            "Without management rules, the replay will use a simple full-position exit. "
            "If you use partials, breakeven, or trailing stops, add those rules explicitly."
        )

    # Behavioral layer summary
    behavioral_rules = [r for r in compiled_rules if r["layer"] == PlanLayer.BEHAVIORAL.value]
    if behavioral_rules:
        suggestions.append(
            f"{len(behavioral_rules)} behavioral rule(s) cannot be replayed historically. "
            "These will be enforced in live trading through Gatekeeper's checklist and journaling."
        )

    # Approximation transparency
    approximated = [r for r in compiled_rules if r["status"] == InterpretationStatus.APPROXIMATED.value]
    if approximated:
        names = ", ".join(f"'{r['name']}'" for r in approximated[:3])
        more = f" and {len(approximated) - 3} more" if len(approximated) > 3 else ""
        suggestions.append(
            f"Rules using approximated interpretations ({names}{more}) may not perfectly reflect "
            "your intent. Review and confirm the proposed proxies before running a replay."
        )

    # Replay readiness
    if replay_readiness == _REPLAY_READY:
        suggestions.append(
            "Your plan is ready for historical replay. All testable rules have been interpreted. "
            "You can run a replay from the validation dashboard."
        )
    elif replay_readiness == _REPLAY_PARTIAL:
        suggestions.append(
            "Your plan is partially ready for replay. Some rules could not be interpreted and will be "
            "treated as always-satisfied during replay. Review the non-testable rules before running."
        )

    return suggestions


def build_report(compiled_plan: CompiledPlan) -> dict:
    """
    Build the full interpretability report from a CompiledPlan.
    This is stored in ValidationRun.feedback and returned in API responses.
    """
    compiled_rules = compiled_plan.compiled_rules
    score = float(compiled_plan.interpretability_score)
    coherence_warnings = compiled_plan.coherence_warnings or []
    replay_readiness = _assess_replay_readiness(compiled_rules)

    total_rules = len(compiled_rules)
    non_behavioral = [r for r in compiled_rules if r["layer"] != PlanLayer.BEHAVIORAL.value]
    testable_count = sum(1 for r in non_behavioral if r["status"] == InterpretationStatus.TESTABLE.value)
    approximated_count = sum(1 for r in non_behavioral if r["status"] == InterpretationStatus.APPROXIMATED.value)
    not_testable_count = sum(1 for r in non_behavioral if r["status"] == InterpretationStatus.NOT_TESTABLE.value)
    behavioral_count = sum(1 for r in compiled_rules if r["layer"] == PlanLayer.BEHAVIORAL.value)

    summary = (
        f"Your plan has {total_rules} rule(s) across "
        f"{len({r['layer'] for r in compiled_rules})} layer(s). "
        f"{testable_count} are directly testable, "
        f"{approximated_count} are approximated, "
        f"{not_testable_count} cannot be tested historically"
        + (f", and {behavioral_count} are behavioral (live enforcement only)" if behavioral_count else "")
        + "."
    )

    layer_data = _layer_breakdown(compiled_rules)
    suggestions = _generate_suggestions(compiled_rules, layer_data, coherence_warnings, score, replay_readiness)

    return {
        "interpretability_score": score,
        "replay_readiness": replay_readiness,
        "summary": summary,
        "rule_counts": {
            "total": total_rules,
            "testable": testable_count,
            "approximated": approximated_count,
            "not_testable": not_testable_count,
            "behavioral": behavioral_count,
        },
        "layer_breakdown": layer_data,
        "coherence_warnings": coherence_warnings,
        "refinement_suggestions": suggestions,
    }
