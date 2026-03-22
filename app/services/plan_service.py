"""
Trading plan + plan rules CRUD service.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import PlanLayer
from app.models.plan_rule import PlanRule
from app.models.trading_plan import TradingPlan

# ── Plan (singleton) ────────────────────────────────────────────────────


async def get_plan(db: AsyncSession) -> TradingPlan:
    result = await db.execute(select(TradingPlan).limit(1))
    plan = result.scalar_one_or_none()
    if plan is None:
        plan = TradingPlan(name="My Trading Plan")
        db.add(plan)
        await db.flush()
    return plan


async def update_plan(db: AsyncSession, *, name: str | None = None, description: str | None = None) -> TradingPlan:
    plan = await get_plan(db)
    if name is not None:
        plan.name = name
    if description is not None:
        plan.description = description
    await db.flush()
    return plan


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
    # Auto-assign order as max+1 in that layer
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
