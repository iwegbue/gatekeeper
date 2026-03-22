"""
Plan compiler — orchestrates the full compilation pipeline for Phase 1.

Responsibilities:
  1. Fetch the current plan and all active rules from the DB.
  2. Build a frozen plan snapshot (for reproducibility).
  3. Call the rule interpreter for each rule.
  4. Run coherence checks on the compiled output.
  5. Compute interpretability score.
  6. Persist CompiledPlan + ValidationRun artifacts.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import InterpretationStatus, PlanLayer, ValidationMode, ValidationRunStatus
from app.models.validation.compiled_plan import CompiledPlan
from app.models.validation.validation_run import ValidationRun
from app.services import plan_service
from app.services.validation.rule_interpreter import interpret_rules

if TYPE_CHECKING:
    from app.services.ai.base import AIProvider

logger = logging.getLogger(__name__)


# ── Plan snapshot ─────────────────────────────────────────────────────────────


def _build_plan_snapshot(plan, rules) -> dict:
    """Freeze the plan state at compile time for reproducibility."""
    return {
        "plan_id": str(plan.id),
        "plan_name": plan.name,
        "plan_description": plan.description,
        "rules": [
            {
                "id": str(r.id),
                "layer": r.layer,
                "name": r.name,
                "description": r.description,
                "rule_type": r.rule_type,
                "weight": r.weight,
                "order": r.order,
                "parameters": r.parameters,
            }
            for r in rules
        ],
    }


def _build_plan_context_text(plan, rules_by_layer: dict) -> str:
    """Build a human-readable plan summary for the AI context."""
    lines = [f"Trading Plan: {plan.name}"]
    if plan.description:
        lines.append(f"Description: {plan.description}")
    lines.append("")
    for layer, layer_rules in rules_by_layer.items():
        if layer_rules:
            lines.append(f"[{layer}]")
            for r in layer_rules:
                lines.append(f"  - ({r.rule_type}, weight={r.weight}) {r.name}")
                if r.description:
                    lines.append(f"      {r.description}")
    return "\n".join(lines)


# ── Interpretability score ────────────────────────────────────────────────────


def _compute_interpretability_score(compiled_rules: list[dict]) -> float:
    """
    Percentage of rules that are TESTABLE or APPROXIMATED.
    BEHAVIORAL / NOT_TESTABLE rules are excluded from the denominator
    only when they are BEHAVIORAL — non-behavioral NOT_TESTABLE rules
    still count against the score.
    """
    scoreable = [r for r in compiled_rules if r["layer"] != PlanLayer.BEHAVIORAL.value]
    if not scoreable:
        return 100.0
    passing = sum(
        1
        for r in scoreable
        if r["status"] in (InterpretationStatus.TESTABLE.value, InterpretationStatus.APPROXIMATED.value)
    )
    return round(passing * 100 / len(scoreable), 2)


# ── Coherence checks ──────────────────────────────────────────────────────────


def _run_coherence_checks(compiled_rules: list[dict]) -> list[str]:
    """
    Deterministic checks on the compiled plan.
    Returns a list of warning strings.
    """
    warnings: list[str] = []
    non_behavioral = [r for r in compiled_rules if r["layer"] != PlanLayer.BEHAVIORAL.value]

    # 1. Gap detection — layers with zero testable/approximated required rules
    layer_testable: dict[str, int] = {layer.value: 0 for layer in PlanLayer if layer != PlanLayer.BEHAVIORAL}
    for r in non_behavioral:
        if r["rule_type"] == "REQUIRED" and r["status"] in (
            InterpretationStatus.TESTABLE.value,
            InterpretationStatus.APPROXIMATED.value,
        ):
            layer_testable[r["layer"]] = layer_testable.get(r["layer"], 0) + 1

    gaps = [layer for layer, count in layer_testable.items() if count == 0]
    if gaps:
        warnings.append(
            f"Layers with no testable required rules: {', '.join(gaps)}. "
            "Historical replay will assume these layers are always satisfied."
        )

    # 2. Underfiltering — fewer than 3 layers have any required rules at all
    layers_with_required = {r["layer"] for r in non_behavioral if r["rule_type"] == "REQUIRED"}
    if len(layers_with_required) < 3:
        warnings.append(
            f"Only {len(layers_with_required)} layer(s) have required rules. "
            "The plan may be underspecified and produce too many signals in replay."
        )

    # 3. Overfiltering — all non-behavioral layers have required rules
    all_non_behavioral_layers = {layer.value for layer in PlanLayer if layer != PlanLayer.BEHAVIORAL}
    if layers_with_required >= all_non_behavioral_layers:
        warnings.append(
            "Every layer has required rules. This may produce very few qualified setups in replay. "
            "Consider whether all requirements are strictly necessary."
        )

    # 4. Redundancy — same proxy type appears more than once in same layer
    seen: dict[str, list[str]] = {}
    for r in non_behavioral:
        if r.get("proxy"):
            key = f"{r['layer']}:{r['proxy']['type']}"
            seen.setdefault(key, []).append(r["name"])
    for key, names in seen.items():
        if len(names) > 1:
            layer, proxy_type = key.split(":", 1)
            warnings.append(
                f"Redundant rules in {layer}: '{' and '.join(names)}' both use proxy type '{proxy_type}'. "
                "Consider merging them."
            )

    # 5. No entry rule
    entry_rules = [r for r in compiled_rules if r["layer"] == PlanLayer.ENTRY.value]
    testable_entry = [r for r in entry_rules if r["status"] != InterpretationStatus.NOT_TESTABLE.value]
    if not testable_entry:
        warnings.append(
            "No testable ENTRY rules found. Replay will use default market-entry (next bar open). "
            "Consider adding an explicit entry rule."
        )

    # 6. No risk rule
    risk_rules = [r for r in compiled_rules if r["layer"] == PlanLayer.RISK.value]
    testable_risk = [r for r in risk_rules if r["status"] != InterpretationStatus.NOT_TESTABLE.value]
    if not testable_risk:
        warnings.append(
            "No testable RISK rules found. Replay requires a stop-loss definition to compute R-multiples. "
            "Consider adding an ATR-based or swing-based stop rule."
        )

    return warnings


# ── Main compile function ─────────────────────────────────────────────────────


async def compile_plan(
    db: AsyncSession,
    provider: "AIProvider",
) -> tuple[CompiledPlan, ValidationRun]:
    """
    Run the full Phase 1 compilation pipeline.

    Returns (compiled_plan, validation_run) — both already flushed to DB.
    The caller (router / get_db context) handles commit.
    """
    plan = await plan_service.get_active_plan(db)
    rules_by_layer = await plan_service.get_rules_by_layer(db, plan.id, active_only=True)
    all_rules = [r for rules in rules_by_layer.values() for r in rules]

    plan_snapshot = _build_plan_snapshot(plan, all_rules)
    plan_context = _build_plan_context_text(plan, rules_by_layer)

    # Compile rules
    now = datetime.now(timezone.utc)
    compiled_rules = await interpret_rules(all_rules, provider, plan_context)

    interpretability_score = _compute_interpretability_score(compiled_rules)
    coherence_warnings = _run_coherence_checks(compiled_rules)

    compiled_plan = CompiledPlan(
        plan_id=plan.id,
        plan_snapshot=plan_snapshot,
        compiled_rules=compiled_rules,
        interpretability_score=interpretability_score,
        coherence_warnings=coherence_warnings,
    )
    db.add(compiled_plan)
    await db.flush()

    run = ValidationRun(
        compiled_plan_id=compiled_plan.id,
        status=ValidationRunStatus.COMPLETED.value,
        mode=ValidationMode.INTERPRETABILITY.value,
        started_at=now,
        completed_at=datetime.now(timezone.utc),
    )
    db.add(run)
    await db.flush()

    return compiled_plan, run


async def confirm_compiled_rule(
    db: AsyncSession,
    compiled_plan_id: uuid.UUID,
    rule_id: str,
    *,
    status: str | None = None,
    proxy_type: str | None = None,
    proxy_params: dict | None = None,
    interpretation_notes: str | None = None,
) -> CompiledPlan | None:
    """
    User confirms or edits an AI-proposed interpretation for a single rule.
    Updates the compiled_rules JSONB in-place and marks user_confirmed=True.
    Returns None if compiled_plan_id or rule_id not found.
    """
    from sqlalchemy import select

    result = await db.execute(select(CompiledPlan).where(CompiledPlan.id == compiled_plan_id))
    compiled_plan = result.scalar_one_or_none()
    if compiled_plan is None:
        return None

    rule_found = False
    updated_rules = []
    for rule in compiled_plan.compiled_rules:
        if rule["rule_id"] == rule_id:
            rule_found = True
            rule = dict(rule)
            rule["user_confirmed"] = True
            if status is not None:
                rule["status"] = status
            if proxy_type is not None:
                from app.services.validation.rule_interpreter import _resolve_feature_dependencies

                params = proxy_params or {}
                rule["proxy"] = None if proxy_type == "not_testable" else {"type": proxy_type, "params": params}
                rule["feature_dependencies"] = _resolve_feature_dependencies(proxy_type, params)
            elif proxy_params is not None and rule.get("proxy"):
                # Update params on existing proxy without changing its type
                rule["proxy"] = {**rule["proxy"], "params": proxy_params}
            if interpretation_notes is not None:
                rule["interpretation_notes"] = interpretation_notes
        updated_rules.append(rule)

    if not rule_found:
        return None

    compiled_plan.compiled_rules = updated_rules
    compiled_plan.interpretability_score = _compute_interpretability_score(updated_rules)
    compiled_plan.coherence_warnings = _run_coherence_checks(updated_rules)

    await db.flush()
    return compiled_plan


async def get_compiled_plan(db: AsyncSession, compiled_plan_id: uuid.UUID) -> CompiledPlan | None:
    from sqlalchemy import select

    result = await db.execute(select(CompiledPlan).where(CompiledPlan.id == compiled_plan_id))
    return result.scalar_one_or_none()


async def list_validation_runs(db: AsyncSession) -> list[ValidationRun]:
    from sqlalchemy import select

    result = await db.execute(select(ValidationRun).order_by(ValidationRun.created_at.desc()))
    return list(result.scalars().all())


async def get_validation_run(db: AsyncSession, run_id: uuid.UUID) -> ValidationRun | None:
    from sqlalchemy import select

    result = await db.execute(select(ValidationRun).where(ValidationRun.id == run_id))
    return result.scalar_one_or_none()
