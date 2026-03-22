"""
Test factory helpers — create test objects with sensible defaults.

Each factory accepts a db session and keyword overrides.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import PlanLayer
from app.models.idea import Idea
from app.models.idea_rule_check import IdeaRuleCheck
from app.models.instrument import Instrument
from app.models.plan_rule import PlanRule
from app.models.trade import Trade
from app.models.trading_plan import TradingPlan


async def create_plan(db: AsyncSession, *, name: str = "Test Plan", description: str | None = None) -> TradingPlan:
    plan = TradingPlan(name=name, description=description)
    db.add(plan)
    await db.flush()
    return plan


async def create_rule(
    db: AsyncSession,
    plan_id: uuid.UUID,
    *,
    layer: str = "CONTEXT",
    name: str = "Test Rule",
    description: str | None = None,
    rule_type: str = "REQUIRED",
    weight: int = 1,
    is_active: bool = True,
    order: int = 0,
) -> PlanRule:
    rule = PlanRule(
        plan_id=plan_id,
        layer=layer,
        name=name,
        description=description,
        rule_type=rule_type,
        weight=weight,
        is_active=is_active,
        order=order,
    )
    db.add(rule)
    await db.flush()
    return rule


async def create_instrument(
    db: AsyncSession,
    *,
    symbol: str = "EURUSD",
    display_name: str = "EUR/USD",
    asset_class: str = "FX",
    is_enabled: bool = True,
) -> Instrument:
    inst = Instrument(
        symbol=symbol,
        display_name=display_name,
        asset_class=asset_class,
        is_enabled=is_enabled,
    )
    db.add(inst)
    await db.flush()
    return inst


async def create_idea(
    db: AsyncSession,
    *,
    instrument: str = "EURUSD",
    direction: str = "LONG",
    state: str = "WATCHING",
    risk_pct: float | None = None,
    notes: str | None = None,
) -> Idea:
    idea = Idea(
        instrument=instrument,
        direction=direction,
        state=state,
        risk_pct=risk_pct,
        notes=notes,
    )
    db.add(idea)
    await db.flush()
    return idea


async def create_idea_with_checks(
    db: AsyncSession,
    plan_id: uuid.UUID,
    *,
    instrument: str = "EURUSD",
    num_rules_per_layer: int = 2,
) -> tuple[Idea, list[IdeaRuleCheck]]:
    """Create an idea with rule checks for each layer (2 REQUIRED rules per layer by default)."""
    idea = await create_idea(db, instrument=instrument)
    checks = []
    for layer in PlanLayer:
        for i in range(num_rules_per_layer):
            rule = await create_rule(db, plan_id, layer=layer.value, name=f"{layer.value} Rule {i+1}", order=i)
            check = IdeaRuleCheck(idea_id=idea.id, rule_id=rule.id)
            db.add(check)
            await db.flush()
            checks.append(check)
    return idea, checks


async def create_trade(
    db: AsyncSession,
    idea_id: uuid.UUID,
    *,
    instrument: str = "EURUSD",
    direction: str = "LONG",
    entry_price: float = 1.1000,
    sl_price: float = 1.0950,
    risk_pct: float = 1.0,
    grade: str = "A",
    state: str = "OPEN",
) -> Trade:
    trade = Trade(
        idea_id=idea_id,
        instrument=instrument,
        direction=direction,
        entry_time=datetime.now(timezone.utc),
        entry_price=entry_price,
        sl_price=sl_price,
        initial_sl_price=sl_price,
        risk_pct=risk_pct,
        grade=grade,
        state=state,
    )
    db.add(trade)
    await db.flush()
    return trade


async def create_full_pipeline(db: AsyncSession) -> dict:
    """Create a complete test pipeline: plan + rules + idea + checks + trade."""
    plan = await create_plan(db)
    idea, checks = await create_idea_with_checks(db, plan.id)
    trade = await create_trade(db, idea.id)
    return {
        "plan": plan,
        "idea": idea,
        "checks": checks,
        "trade": trade,
    }
