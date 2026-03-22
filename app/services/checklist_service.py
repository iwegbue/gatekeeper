"""
Checklist service — manages idea rule checks, computes scores/grades,
and determines layer completion for the state machine.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import PlanLayer, RuleType, SetupGrade
from app.models.idea import Idea
from app.models.idea_rule_check import IdeaRuleCheck
from app.models.plan_rule import PlanRule

# ── Grade thresholds ─────────────────────────────────────────────────────
GRADE_A_THRESHOLD = 85  # >= 85% → A
GRADE_B_THRESHOLD = 65  # 65–84% → B
# < 65% → C


async def initialize_checks(db: AsyncSession, idea_id: uuid.UUID, plan_id: uuid.UUID) -> list[IdeaRuleCheck]:
    """
    Create one IdeaRuleCheck per active plan rule for a new idea.
    Called when an idea is first created.
    """
    rules_result = await db.execute(
        select(PlanRule).where(
            PlanRule.plan_id == plan_id,
            PlanRule.is_active.is_(True),
        )
    )
    rules = list(rules_result.scalars().all())

    checks = []
    for rule in rules:
        check = IdeaRuleCheck(idea_id=idea_id, rule_id=rule.id, checked=False)
        db.add(check)
        checks.append(check)
    await db.flush()
    return checks


async def get_checks(db: AsyncSession, idea_id: uuid.UUID) -> list[IdeaRuleCheck]:
    result = await db.execute(
        select(IdeaRuleCheck).where(IdeaRuleCheck.idea_id == idea_id)
    )
    return list(result.scalars().all())


async def get_checks_with_rules(db: AsyncSession, idea_id: uuid.UUID) -> list[tuple[IdeaRuleCheck, PlanRule]]:
    """Return (check, rule) pairs for an idea, ordered by layer and rule order."""
    result = await db.execute(
        select(IdeaRuleCheck, PlanRule)
        .join(PlanRule, IdeaRuleCheck.rule_id == PlanRule.id)
        .where(IdeaRuleCheck.idea_id == idea_id)
        .order_by(PlanRule.layer, PlanRule.order)
    )
    return list(result.all())


async def toggle_check(db: AsyncSession, check_id: uuid.UUID, checked: bool, notes: str | None = None) -> IdeaRuleCheck | None:
    result = await db.execute(select(IdeaRuleCheck).where(IdeaRuleCheck.id == check_id))
    check = result.scalar_one_or_none()
    if check is None:
        return None
    check.checked = checked
    check.checked_at = datetime.now(timezone.utc) if checked else None
    if notes is not None:
        check.notes = notes
    await db.flush()
    return check


async def compute_score(db: AsyncSession, idea_id: uuid.UUID) -> tuple[int, int]:
    """
    Compute (achieved_score, max_score) from checked REQUIRED/OPTIONAL rules.
    ADVISORY rules (weight=0 or rule_type=ADVISORY) are excluded from scoring.
    Returns the percentage score (0-100).
    """
    pairs = await get_checks_with_rules(db, idea_id)

    total_weight = 0
    checked_weight = 0

    for check, rule in pairs:
        if rule.rule_type == RuleType.ADVISORY:
            continue
        total_weight += rule.weight
        if check.checked:
            checked_weight += rule.weight

    return checked_weight, total_weight


async def compute_grade(db: AsyncSession, idea_id: uuid.UUID) -> SetupGrade | None:
    """Compute grade from current check state. Returns None if no scoreable rules."""
    checked_weight, total_weight = await compute_score(db, idea_id)
    if total_weight == 0:
        return None
    pct = int(checked_weight * 100 / total_weight)
    if pct >= GRADE_A_THRESHOLD:
        return SetupGrade.A
    if pct >= GRADE_B_THRESHOLD:
        return SetupGrade.B
    return SetupGrade.C


async def update_idea_score(db: AsyncSession, idea: Idea) -> Idea:
    """Recompute and persist checklist_score and grade on an idea."""
    checked_weight, total_weight = await compute_score(db, idea.id)
    grade = await compute_grade(db, idea.id)
    idea.checklist_score = int(checked_weight * 100 / total_weight) if total_weight > 0 else 0
    idea.grade = grade.value if grade else None
    await db.flush()
    return idea


async def get_layer_completion(db: AsyncSession, idea_id: uuid.UUID) -> dict[str, bool]:
    """
    Returns {layer: is_complete} for each PlanLayer.
    A layer is complete when all REQUIRED rules in it are checked.
    Layers with no REQUIRED rules are considered complete.
    """
    pairs = await get_checks_with_rules(db, idea_id)

    # Build per-layer required/checked counts
    required: dict[str, int] = {layer.value: 0 for layer in PlanLayer}
    checked: dict[str, int] = {layer.value: 0 for layer in PlanLayer}

    for check, rule in pairs:
        if rule.rule_type != RuleType.REQUIRED:
            continue
        required[rule.layer] = required.get(rule.layer, 0) + 1
        if check.checked:
            checked[rule.layer] = checked.get(rule.layer, 0) + 1

    return {
        layer.value: (required[layer.value] == 0 or checked[layer.value] >= required[layer.value])
        for layer in PlanLayer
    }


async def get_layer_blockers(db: AsyncSession, idea_id: uuid.UUID, layer: str) -> list[str]:
    """Return names of unchecked REQUIRED rules in a given layer."""
    pairs = await get_checks_with_rules(db, idea_id)
    return [
        rule.name
        for check, rule in pairs
        if rule.layer == layer and rule.rule_type == RuleType.REQUIRED and not check.checked
    ]
