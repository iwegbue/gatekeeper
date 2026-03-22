"""
Trading plan + plan rules CRUD service.

Supports multiple plans with exactly one active at a time.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import PlanLayer
from app.models.plan_rule import PlanRule
from app.models.trading_plan import TradingPlan

# ── Plan CRUD ────────────────────────────────────────────────────────────


async def get_plan(db: AsyncSession) -> TradingPlan:
    """Return the active plan, creating one if none exist (backward compat)."""
    return await get_active_plan(db)


async def get_active_plan(db: AsyncSession) -> TradingPlan:
    """Return the active plan. If no plans exist, create a default active one."""
    result = await db.execute(select(TradingPlan).where(TradingPlan.is_active.is_(True)).limit(1))
    plan = result.scalar_one_or_none()
    if plan is None:
        plan = TradingPlan(name="My Trading Plan", is_active=True)
        db.add(plan)
        await db.flush()
    return plan


async def get_plan_by_id(db: AsyncSession, plan_id: uuid.UUID) -> TradingPlan | None:
    result = await db.execute(select(TradingPlan).where(TradingPlan.id == plan_id))
    return result.scalar_one_or_none()


async def list_plans(db: AsyncSession) -> list[TradingPlan]:
    result = await db.execute(select(TradingPlan).order_by(TradingPlan.created_at.asc()))
    return list(result.scalars().all())


async def create_plan(
    db: AsyncSession,
    *,
    name: str,
    description: str | None = None,
    activate: bool = False,
) -> TradingPlan:
    """Create a new trading plan. If activate=True, deactivate all others first."""
    if activate:
        await _deactivate_all(db)

    plan = TradingPlan(name=name, description=description, is_active=activate)
    db.add(plan)
    await db.flush()
    return plan


async def update_plan(
    db: AsyncSession,
    *,
    plan_id: uuid.UUID | None = None,
    name: str | None = None,
    description: str | None = None,
) -> TradingPlan | None:
    """Update plan metadata. If plan_id is None, updates the active plan.
    Returns None if a specific plan_id was given but not found."""
    if plan_id is not None:
        plan = await get_plan_by_id(db, plan_id)
        if plan is None:
            return None
    else:
        plan = await get_active_plan(db)
    if name is not None:
        plan.name = name
    if description is not None:
        plan.description = description
    await db.flush()
    return plan


async def activate_plan(db: AsyncSession, plan_id: uuid.UUID) -> TradingPlan | None:
    """Set plan_id as the active plan, deactivating all others."""
    plan = await get_plan_by_id(db, plan_id)
    if plan is None:
        return None
    await _deactivate_all(db)
    plan.is_active = True
    await db.flush()
    return plan


async def delete_plan(db: AsyncSession, plan_id: uuid.UUID) -> str | None:
    """Delete a plan. Returns None on success, or an error reason string.

    Blocked if:
    - Plan not found → None (treat as already gone)
    - Plan is active → 'active'
    - Plan has ideas referencing it → 'has_ideas'
    """
    from app.models.idea import Idea

    plan = await get_plan_by_id(db, plan_id)
    if plan is None:
        return None
    if plan.is_active:
        return "active"
    idea_count_result = await db.execute(
        select(func.count()).select_from(Idea).where(Idea.plan_id == plan_id)
    )
    if (idea_count_result.scalar() or 0) > 0:
        return "has_ideas"
    await db.delete(plan)
    await db.flush()
    return None


async def duplicate_plan(
    db: AsyncSession,
    source_plan_id: uuid.UUID,
    *,
    name: str | None = None,
) -> TradingPlan | None:
    """Create a copy of an existing plan with all its rules."""
    source = await get_plan_by_id(db, source_plan_id)
    if source is None:
        return None

    new_plan = TradingPlan(
        name=name or f"{source.name} (copy)",
        description=source.description,
        is_active=False,
    )
    db.add(new_plan)
    await db.flush()

    rules = await get_rules(db, source_plan_id, active_only=False)
    for rule in rules:
        new_rule = PlanRule(
            plan_id=new_plan.id,
            layer=rule.layer,
            name=rule.name,
            description=rule.description,
            rule_type=rule.rule_type,
            weight=rule.weight,
            order=rule.order,
            is_active=rule.is_active,
            parameters=rule.parameters,
        )
        db.add(new_rule)
    await db.flush()
    return new_plan


async def _deactivate_all(db: AsyncSession) -> None:
    result = await db.execute(select(TradingPlan).where(TradingPlan.is_active.is_(True)))
    for plan in result.scalars().all():
        plan.is_active = False
    await db.flush()


# ── Rules ────────────────────────────────────────────────────────────────


async def get_rules(
    db: AsyncSession, plan_id: uuid.UUID, *, layer: str | None = None, active_only: bool = True
) -> list[PlanRule]:
    stmt = select(PlanRule).where(PlanRule.plan_id == plan_id)
    if layer:
        stmt = stmt.where(PlanRule.layer == layer)
    if active_only:
        stmt = stmt.where(PlanRule.is_active.is_(True))
    stmt = stmt.order_by(PlanRule.layer, PlanRule.order, PlanRule.created_at)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_rules_by_layer(
    db: AsyncSession, plan_id: uuid.UUID, active_only: bool = True
) -> dict[str, list[PlanRule]]:
    rules = await get_rules(db, plan_id, active_only=active_only)
    by_layer: dict[str, list[PlanRule]] = {layer.value: [] for layer in PlanLayer}
    for rule in rules:
        by_layer.setdefault(rule.layer, []).append(rule)
    return by_layer


async def get_rule(db: AsyncSession, rule_id: uuid.UUID) -> PlanRule | None:
    result = await db.execute(select(PlanRule).where(PlanRule.id == rule_id))
    return result.scalar_one_or_none()


async def get_rule_for_plan(db: AsyncSession, rule_id: uuid.UUID, plan_id: uuid.UUID) -> PlanRule | None:
    """Return a rule only if it belongs to the given plan."""
    result = await db.execute(
        select(PlanRule).where(PlanRule.id == rule_id, PlanRule.plan_id == plan_id)
    )
    return result.scalar_one_or_none()


async def create_rule(
    db: AsyncSession,
    plan_id: uuid.UUID,
    *,
    layer: str,
    name: str,
    description: str | None = None,
    rule_type: str = "REQUIRED",
    weight: int = 1,
    parameters: dict | None = None,
) -> PlanRule:
    result = await db.execute(
        select(func.coalesce(func.max(PlanRule.order), 0)).where(PlanRule.plan_id == plan_id, PlanRule.layer == layer)
    )
    max_order = result.scalar() or 0

    rule = PlanRule(
        plan_id=plan_id,
        layer=layer,
        name=name,
        description=description,
        rule_type=rule_type,
        weight=weight,
        order=max_order + 1,
        parameters=parameters,
    )
    db.add(rule)
    await db.flush()
    return rule


async def update_rule(
    db: AsyncSession,
    rule_id: uuid.UUID,
    **kwargs,
) -> PlanRule | None:
    rule = await get_rule(db, rule_id)
    if rule is None:
        return None
    protected = ("id", "plan_id", "layer", "created_at")
    for key, value in kwargs.items():
        if hasattr(rule, key) and key not in protected:
            setattr(rule, key, value)
    await db.flush()
    return rule


async def delete_rule(db: AsyncSession, rule_id: uuid.UUID) -> bool:
    rule = await get_rule(db, rule_id)
    if rule is None:
        return False
    await db.delete(rule)
    await db.flush()
    return True


async def clear_rules(db: AsyncSession, plan_id: uuid.UUID) -> int:
    """Delete all rules for a plan. Returns the count of deleted rules."""
    result = await db.execute(select(PlanRule).where(PlanRule.plan_id == plan_id))
    rules = list(result.scalars().all())
    for rule in rules:
        await db.delete(rule)
    await db.flush()
    return len(rules)


async def reorder_rules(db: AsyncSession, plan_id: uuid.UUID, layer: str, rule_ids: list[uuid.UUID]) -> None:
    for idx, rid in enumerate(rule_ids):
        result = await db.execute(
            select(PlanRule).where(PlanRule.id == rid, PlanRule.plan_id == plan_id, PlanRule.layer == layer)
        )
        rule = result.scalar_one_or_none()
        if rule:
            rule.order = idx
    await db.flush()
