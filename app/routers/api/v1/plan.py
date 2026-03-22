import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.base import SuccessResponse
from app.schemas.plan import PlanResponse, PlanRuleCreate, PlanRuleResponse, PlanRuleUpdate
from app.services import plan_service

router = APIRouter(prefix="/plan", tags=["plan"])


@router.get("", response_model=PlanResponse)
async def get_plan(db: AsyncSession = Depends(get_db)):
    plan = await plan_service.get_plan(db)
    rules_by_layer = await plan_service.get_rules_by_layer(db, plan.id)
    return PlanResponse(
        id=plan.id,
        name=plan.name,
        description=plan.description,
        rules_by_layer={
            layer: [PlanRuleResponse.model_validate(r) for r in rules] for layer, rules in rules_by_layer.items()
        },
    )


@router.get("/rules", response_model=list[PlanRuleResponse])
async def list_rules(
    layer: str | None = None,
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
):
    plan = await plan_service.get_plan(db)
    rules = await plan_service.get_rules(db, plan.id, layer=layer, active_only=active_only)
    return [PlanRuleResponse.model_validate(r) for r in rules]


@router.post("/rules", response_model=PlanRuleResponse, status_code=201)
async def create_rule(body: PlanRuleCreate, db: AsyncSession = Depends(get_db)):
    plan = await plan_service.get_plan(db)
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


@router.patch("/rules/{rule_id}", response_model=PlanRuleResponse)
async def update_rule(
    rule_id: uuid.UUID,
    body: PlanRuleUpdate,
    db: AsyncSession = Depends(get_db),
):
    update_data = body.model_dump(exclude_unset=True)
    rule = await plan_service.update_rule(db, rule_id, **update_data)
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    return PlanRuleResponse.model_validate(rule)


@router.delete("/rules/{rule_id}", response_model=SuccessResponse)
async def delete_rule(rule_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    deleted = await plan_service.delete_rule(db, rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Rule not found")
    return SuccessResponse(message="Rule deleted")
