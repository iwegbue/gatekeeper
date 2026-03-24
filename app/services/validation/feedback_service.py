"""
Feedback service — transforms a CompiledPlan into a structured,
human-readable validation report.

This is the output layer for Phase 1 (interpretability). It produces:
  - Per-layer breakdown of rule replay coverage
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

# Statuses that mean a rule can be evaluated from OHLC data
_REPLAYABLE_STATUSES = {
    InterpretationStatus.OHLC_COMPUTABLE.value,
    InterpretationStatus.OHLC_APPROXIMATE.value,
    # Legacy aliases for runs compiled before the redesign
    InterpretationStatus.TESTABLE.value,
    InterpretationStatus.APPROXIMATED.value,
}

# Statuses that mean the rule can only be enforced during live trading
_LIVE_ONLY_STATUSES = {
    InterpretationStatus.LIVE_ONLY.value,
    InterpretationStatus.NOT_TESTABLE.value,  # legacy alias
}


def _layer_breakdown(compiled_rules: list[dict]) -> dict:
    """Per-layer count of rule replay coverage."""
    breakdown: dict[str, dict] = {}
    for layer in PlanLayer:
        breakdown[layer.value] = {
            "replayable": 0,
            "approximate": 0,
            "live_only": 0,
            "behavioral": layer == PlanLayer.BEHAVIORAL,
            "rules": [],
        }

    for rule in compiled_rules:
        layer = rule["layer"]
        status = rule["status"]
        if layer not in breakdown:
            breakdown[layer] = {"replayable": 0, "approximate": 0, "live_only": 0, "behavioral": False, "rules": []}

        if status in {InterpretationStatus.OHLC_COMPUTABLE.value, InterpretationStatus.TESTABLE.value}:
            breakdown[layer]["replayable"] += 1
        elif status in {InterpretationStatus.OHLC_APPROXIMATE.value, InterpretationStatus.APPROXIMATED.value}:
            breakdown[layer]["approximate"] += 1
        else:
            breakdown[layer]["live_only"] += 1

        breakdown[layer]["rules"].append(
            {
                "name": rule["name"],
                "rule_type": rule["rule_type"],
                "status": status,
                "data_sources_required": rule.get("data_sources_required") or [],
                "confidence": rule.get("confidence"),
                "interpretation_notes": rule.get("interpretation_notes", ""),
                "user_confirmed": rule.get("user_confirmed", False),
                "live_only": (
                    status in _LIVE_ONLY_STATUSES
                    or layer == PlanLayer.BEHAVIORAL.value
                ),
            }
        )

    return breakdown


def _assess_replay_readiness(compiled_rules: list[dict]) -> str:
    """
    Determine overall replay readiness.
    READY     — all non-behavioral rules are OHLC_COMPUTABLE or OHLC_APPROXIMATE.
    PARTIAL   — some rules are replayable but important gaps exist.
    NOT_READY — no replayable rules, or RISK layer is fully live-only.
    """
    non_behavioral = [r for r in compiled_rules if r["layer"] != PlanLayer.BEHAVIORAL.value]
    if not non_behavioral:
        return _REPLAY_NOT_READY

    replayable_count = sum(1 for r in non_behavioral if r["status"] in _REPLAYABLE_STATUSES)

    risk_rules = [r for r in compiled_rules if r["layer"] == PlanLayer.RISK.value]
    has_replayable_risk = any(r["status"] in _REPLAYABLE_STATUSES for r in risk_rules)

    if replayable_count == 0:
        return _REPLAY_NOT_READY
    if not has_replayable_risk:
        return _REPLAY_NOT_READY
    if replayable_count == len(non_behavioral):
        return _REPLAY_READY
    return _REPLAY_PARTIAL


def _generate_suggestions(
    compiled_rules: list[dict],
    layer_data: dict,
    coherence_warnings: list[str],
    interpretability_score: float,
    replay_readiness: str,
    replayable_rules: list[dict] | None = None,
    live_only_rules: list[dict] | None = None,
) -> list[str]:
    """Generate actionable refinement suggestions."""
    suggestions: list[str] = []

    # Score-based
    if interpretability_score < 40:
        suggestions.append(
            "More than half of your rules can only be evaluated during live trading. "
            "If you want historical replay coverage, consider whether any of these rules "
            "could be expressed using price, volume, or a standard indicator "
            "(e.g., 'RSI(14) above 50 on the 1H chart' or 'price within 0.5 ATR of prior swing high')."
        )
    elif interpretability_score < 70:
        suggestions.append(
            "Several rules were classified as approximate. Review the interpretation notes "
            "for each rule and confirm whether the classification captures your intent."
        )

    # Layer-specific: all rules in a non-behavioral layer are live-only
    for layer_name, data in layer_data.items():
        if layer_name == PlanLayer.BEHAVIORAL.value:
            continue
        total = data["replayable"] + data["approximate"] + data["live_only"]
        if total > 0 and data["live_only"] == total:
            suggestions.append(
                f"All rules in the {layer_name} layer will be enforced during live trading only. "
                "If you want replay coverage for this layer, consider whether any rule "
                "can be expressed using OHLC data or a standard indicator."
            )

    # Risk layer
    risk_data = layer_data.get(PlanLayer.RISK.value, {})
    if risk_data.get("live_only", 0) > 0 and risk_data.get("replayable", 0) == 0:
        suggestions.append(
            "Your RISK layer has no replayable stop-loss rule. "
            "Without a replayable stop, replay cannot compute R-multiples. "
            "Consider adding an ATR-based or swing-based stop rule."
        )

    # Management
    mgmt_data = layer_data.get(PlanLayer.MANAGEMENT.value, {})
    mgmt_replayable = mgmt_data.get("replayable", 0) + mgmt_data.get("approximate", 0)
    if mgmt_replayable == 0:
        suggestions.append(
            "No replayable MANAGEMENT rules were found. "
            "Without management rules, the replay will use a simple full-position exit. "
            "If you use partials, breakeven, or trailing stops, add those rules explicitly."
        )

    # Behavioral layer summary
    behavioral_rules = [r for r in compiled_rules if r["layer"] == PlanLayer.BEHAVIORAL.value]
    if behavioral_rules:
        suggestions.append(
            f"{len(behavioral_rules)} behavioral rule(s) are tracked via live journaling and checklist, "
            "not included in historical replay."
        )

    # Approximate transparency
    approximate = [r for r in compiled_rules if r["status"] in {
        InterpretationStatus.OHLC_APPROXIMATE.value,
        InterpretationStatus.APPROXIMATED.value,
    }]
    if approximate:
        names = ", ".join(f"'{r['name']}'" for r in approximate[:3])
        more = f" and {len(approximate) - 3} more" if len(approximate) > 3 else ""
        suggestions.append(
            f"Rules with approximate OHLC coverage ({names}{more}) may not perfectly reflect "
            "your intent. Review the interpretation notes and confirm before running a replay."
        )

    # Replay readiness
    if replay_readiness == _REPLAY_READY:
        suggestions.append(
            "Your plan is ready for historical replay. All non-behavioral rules have OHLC coverage. "
            "You can run a replay from the validation dashboard."
        )
    elif replay_readiness == _REPLAY_PARTIAL:
        replayable_count = len(replayable_rules) if replayable_rules else 0
        non_behavioral = [r for r in compiled_rules if r["layer"] != PlanLayer.BEHAVIORAL.value]
        non_behavioral_count = len(non_behavioral)
        suggestions.append(
            f"Your replay will cover {replayable_count} of {non_behavioral_count} non-behavioral rules. "
            "The remaining rules will be evaluated during live trading."
        )

    return suggestions


def _compute_verdict(
    interpretability_score: float,
    coherence_warnings: list[str],
    replay_readiness: str,
) -> dict:
    """
    Produce a simple traffic-light verdict a casual trader can act on.
    Returns {"level": "good"|"warning"|"issues", "headline": str, "detail": str}
    """
    warning_count = len(coherence_warnings)

    if interpretability_score >= 70 and warning_count == 0:
        return {
            "level": "good",
            "headline": "Your plan looks solid",
            "detail": "No structural issues found. Your rules are clear and well-structured.",
        }
    elif interpretability_score >= 40 and warning_count <= 2:
        return {
            "level": "warning",
            "headline": "Your plan has a few gaps",
            "detail": "Some rules or layers could be clearer. See the suggestions below.",
        }
    else:
        return {
            "level": "issues",
            "headline": "Your plan needs some work",
            "detail": "Several issues were found. Review the suggestions below to strengthen your plan.",
        }


def _plain_suggestions(
    compiled_rules: list[dict],
    layer_data: dict,
    coherence_warnings: list[str],
    interpretability_score: float,
) -> list[str]:
    """
    Return a short, plain-English list of things the trader should do.
    Avoids OHLC/replay/interpretability jargon entirely.
    """
    suggestions: list[str] = []

    # Structural gaps from coherence checks — rephrase in plain English
    for warning in coherence_warnings:
        w = warning.lower()
        if "no replayable required rules" in w or "no replayable" in w:
            # Extract the layer names mentioned
            if "entry" in w:
                suggestions.append(
                    "Your Entry layer has no concrete entry rule. Add a specific entry condition "
                    "(e.g. a price level, pattern, or signal) so your plan is unambiguous."
                )
            elif "risk" in w:
                suggestions.append(
                    "Your Risk layer has no stop-loss rule. Add a rule that defines exactly where "
                    "you exit if the trade goes against you."
                )
            else:
                # Generic gap — extract layer list from coherence warning
                suggestions.append(
                    "Some layers have no concrete required rules. Make sure every key layer "
                    "(Context, Setup, Entry, Risk) has at least one rule that must be met."
                )
        elif "underspecified" in w or "fewer than" in w or "only" in w and "layer" in w:
            suggestions.append(
                "Your plan doesn't have required rules in enough layers. A complete plan should "
                "cover at least Context, Setup, Entry, and Risk."
            )
        elif "every layer has required rules" in w or "overfiltering" in w or "overspecified" in w:
            suggestions.append(
                "Your plan may be over-specified — every layer has required rules. "
                "Consider whether all requirements are truly mandatory, or whether some "
                "could be Optional instead."
            )

    # Rules that can't be verified at all — too vague
    live_only_non_behavioral = [
        r for r in compiled_rules
        if r["layer"] != PlanLayer.BEHAVIORAL.value
        and r["status"] in {InterpretationStatus.LIVE_ONLY.value, InterpretationStatus.NOT_TESTABLE.value}
    ]
    if len(live_only_non_behavioral) >= 3:
        suggestions.append(
            f"{len(live_only_non_behavioral)} of your rules are too vague to be verified objectively. "
            "Try making them more specific — use concrete price levels, indicator values, "
            "or observable conditions rather than subjective judgments."
        )

    # Risk layer fully unverifiable
    risk_rules = [r for r in compiled_rules if r["layer"] == PlanLayer.RISK.value]
    if risk_rules and all(
        r["status"] in {InterpretationStatus.LIVE_ONLY.value, InterpretationStatus.NOT_TESTABLE.value}
        for r in risk_rules
    ):
        suggestions.append(
            "Your stop-loss rule is too vague to be verified. "
            "Define it concretely — for example: 'Stop below the last swing low' or "
            "'Stop at 1× ATR(14) below entry'."
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
    replayable_count = sum(1 for r in non_behavioral if r["status"] in {
        InterpretationStatus.OHLC_COMPUTABLE.value, InterpretationStatus.TESTABLE.value
    })
    approximate_count = sum(1 for r in non_behavioral if r["status"] in {
        InterpretationStatus.OHLC_APPROXIMATE.value, InterpretationStatus.APPROXIMATED.value
    })
    live_only_count = sum(1 for r in non_behavioral if r["status"] in _LIVE_ONLY_STATUSES)
    behavioral_count = sum(1 for r in compiled_rules if r["layer"] == PlanLayer.BEHAVIORAL.value)

    summary = (
        f"Your plan has {total_rules} rule(s) across "
        f"{len({r['layer'] for r in compiled_rules})} layer(s). "
        f"{replayable_count} can be replayed from OHLC data, "
        f"{approximate_count} have approximate OHLC coverage, "
        f"{live_only_count} are enforced live"
        + (f", and {behavioral_count} are behavioral (live enforcement only)" if behavioral_count else "")
        + "."
    )

    # Build replayable and live-only rule lists
    replayable_rules = [
        {
            "name": r["name"],
            "layer": r["layer"],
            "data_sources_required": r.get("data_sources_required") or [],
        }
        for r in compiled_rules
        if r["layer"] != PlanLayer.BEHAVIORAL.value and r["status"] in _REPLAYABLE_STATUSES
    ]
    live_only_rules = [
        {
            "name": r["name"],
            "layer": r["layer"],
            "reason": "behavioral" if r["layer"] == PlanLayer.BEHAVIORAL.value else "live_judgment",
        }
        for r in compiled_rules
        if r["layer"] == PlanLayer.BEHAVIORAL.value or r["status"] in _LIVE_ONLY_STATUSES
    ]

    layer_data = _layer_breakdown(compiled_rules)
    suggestions = _generate_suggestions(
        compiled_rules, layer_data, coherence_warnings, score, replay_readiness,
        replayable_rules=replayable_rules, live_only_rules=live_only_rules,
    )
    plain_suggestions = _plain_suggestions(compiled_rules, layer_data, coherence_warnings, score)
    verdict = _compute_verdict(score, coherence_warnings, replay_readiness)

    return {
        "interpretability_score": score,
        "replay_readiness": replay_readiness,
        "verdict": verdict,
        "plain_suggestions": plain_suggestions,
        "summary": summary,
        "rule_counts": {
            "total": total_rules,
            "replayable": replayable_count,
            "approximate": approximate_count,
            "live_only": live_only_count,
            "behavioral": behavioral_count,
        },
        "layer_breakdown": layer_data,
        "coherence_warnings": coherence_warnings,
        "refinement_suggestions": suggestions,
        "replayable_rules": replayable_rules,
        "live_only_rules": live_only_rules,
    }
