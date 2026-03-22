import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.base import SuccessResponse
from app.schemas.plan import (
    PlanCreate,
    PlanResponse,
    PlanRuleCreate,
    PlanRuleResponse,
    PlanRuleUpdate,
    PlanSummaryResponse,
    PlanUpdate,
)
from app.services import plan_service

router = APIRouter(prefix="/plans", tags=["plans"])


# ── Plan CRUD ─────────────────────────────────────────────────────────────────


@router.get("", response_model=list[PlanSummaryResponse])
async def list_plans(db: AsyncSession = Depends(get_db)):
    plans = await plan_service.list_plans(db)
    return [PlanSummaryResponse.model_validate(p) for p in plans]


@router.post("", response_model=PlanSummaryResponse, status_code=201)
async def create_plan(body: PlanCreate, db: AsyncSession = Depends(get_db)):
    plan = await plan_service.create_plan(
        db, name=body.name, description=body.description, activate=body.activate
    )
    return PlanSummaryResponse.model_validate(plan)


@router.get("/active", response_model=PlanResponse)
async def get_active_plan(db: AsyncSession = Depends(get_db)):
    plan = await plan_service.get_active_plan(db)
    rules_by_layer = await plan_service.get_rules_by_layer(db, plan.id)
    return PlanResponse(
        id=plan.id,
        name=plan.name,
        description=plan.description,
        is_active=plan.is_active,
        rules_by_layer={
            layer: [PlanRuleResponse.model_validate(r) for r in rules] for layer, rules in rules_by_layer.items()
        },
    )


@router.get("/{plan_id}", response_model=PlanResponse)
async def get_plan(plan_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    plan = await plan_service.get_plan_by_id(db, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    rules_by_layer = await plan_service.get_rules_by_layer(db, plan.id)
    return PlanResponse(
        id=plan.id,
        name=plan.name,
        description=plan.description,
        is_active=plan.is_active,
        rules_by_layer={
            layer: [PlanRuleResponse.model_validate(r) for r in rules] for layer, rules in rules_by_layer.items()
        },
    )


@router.patch("/{plan_id}", response_model=PlanSummaryResponse)
async def update_plan(plan_id: uuid.UUID, body: PlanUpdate, db: AsyncSession = Depends(get_db)):
    plan = await plan_service.update_plan(
        db, plan_id=plan_id, name=body.name, description=body.description
    )
    return PlanSummaryResponse.model_validate(plan)


@router.post("/{plan_id}/activate", response_model=PlanSummaryResponse)
async def activate_plan(plan_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    plan = await plan_service.activate_plan(db, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    return PlanSummaryResponse.model_validate(plan)


@router.delete("/{plan_id}", response_model=SuccessResponse)
async def delete_plan(plan_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    deleted = await plan_service.delete_plan(db, plan_id)
    if not deleted:
        raise HTTPException(status_code=409, detail="Cannot delete active plan")
    return SuccessResponse(message="Plan deleted")


@router.post("/{plan_id}/duplicate", response_model=PlanSummaryResponse, status_code=201)
async def duplicate_plan(plan_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    plan = await plan_service.duplicate_plan(db, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    return PlanSummaryResponse.model_validate(plan)


# ── Rules ─────────────────────────────────────────────────────────────────────


@router.get("/{plan_id}/rules", response_model=list[PlanRuleResponse])
async def list_rules(
    plan_id: uuid.UUID,
    layer: str | None = None,
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
):
    plan = await plan_service.get_plan_by_id(db, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    rules = await plan_service.get_rules(db, plan.id, layer=layer, active_only=active_only)
    return [PlanRuleResponse.model_validate(r) for r in rules]


@router.post("/{plan_id}/rules", response_model=PlanRuleResponse, status_code=201)
async def create_rule(plan_id: uuid.UUID, body: PlanRuleCreate, db: AsyncSession = Depends(get_db)):
    plan = await plan_service.get_plan_by_id(db, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    rule = await plan_service.create_rule(
        db,
        plan.id,
        layer=body.layer,
        name=body.name,
        description=body.description,
        rule_type=body.rule_type,
        weight=body.weight,
        parameters=body.parameters,
    )
    return PlanRuleResponse.model_validate(rule)


@router.patch("/{plan_id}/rules/{rule_id}", response_model=PlanRuleResponse)
async def update_rule(
    plan_id: uuid.UUID,
    rule_id: uuid.UUID,
    body: PlanRuleUpdate,
    db: AsyncSession = Depends(get_db),
):
    update_data = body.model_dump(exclude_unset=True)
    rule = await plan_service.update_rule(db, rule_id, **update_data)
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    return PlanRuleResponse.model_validate(rule)


@router.delete("/{plan_id}/rules/{rule_id}", response_model=SuccessResponse)
async def delete_rule(plan_id: uuid.UUID, rule_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    deleted = await plan_service.delete_rule(db, rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Rule not found")
    return SuccessResponse(message="Rule deleted")


# ── Backward-compatible aliases ───────────────────────────────────────────────
# These keep the old /api/v1/plan endpoints working for existing clients.

compat_router = APIRouter(prefix="/plan", tags=["plan-compat"])


@compat_router.get("", response_model=PlanResponse)
async def compat_get_plan(db: AsyncSession = Depends(get_db)):
    """Backward-compatible: returns the active plan."""
    return await get_active_plan(db)


@compat_router.get("/rules", response_model=list[PlanRuleResponse])
async def compat_list_rules(
    layer: str | None = None,
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
):
    plan = await plan_service.get_active_plan(db)
    rules = await plan_service.get_rules(db, plan.id, layer=layer, active_only=active_only)
    return [PlanRuleResponse.model_validate(r) for r in rules]


@compat_router.post("/rules", response_model=PlanRuleResponse, status_code=201)
async def compat_create_rule(body: PlanRuleCreate, db: AsyncSession = Depends(get_db)):
    plan = await plan_service.get_active_plan(db)
    rule = await plan_service.create_rule(
        db,
        plan.id,
        layer=body.layer,
        name=body.name,
        description=body.description,
        rule_type=body.rule_type,
        weight=body.weight,
        parameters=body.parameters,
    )
    return PlanRuleResponse.model_validate(rule)


@compat_router.patch("/rules/{rule_id}", response_model=PlanRuleResponse)
async def compat_update_rule(
    rule_id: uuid.UUID,
    body: PlanRuleUpdate,
    db: AsyncSession = Depends(get_db),
):
    update_data = body.model_dump(exclude_unset=True)
    rule = await plan_service.update_rule(db, rule_id, **update_data)
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    return PlanRuleResponse.model_validate(rule)


@compat_router.delete("/rules/{rule_id}", response_model=SuccessResponse)
async def compat_delete_rule(rule_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    deleted = await plan_service.delete_rule(db, rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Rule not found")
    return SuccessResponse(message="Rule deleted")
