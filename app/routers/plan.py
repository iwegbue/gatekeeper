import uuid

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import RedirectResponse

from app.csrf import require_csrf
from app.database import get_db
from app.models.enums import PlanLayer, RuleType
from app.services import plan_service

router = APIRouter(prefix="/plan")


@router.get("")
async def plan_index(request: Request, db: AsyncSession = Depends(get_db)):
    plan = await plan_service.get_plan(db)
    rules_by_layer = await plan_service.get_rules_by_layer(db, plan.id)
    return request.app.state.templates.TemplateResponse(
        "plan/index.html",
        {
            "request": request,
            "plan": plan,
            "rules_by_layer": rules_by_layer,
            "layers": PlanLayer,
            "rule_types": RuleType,
        },
    )


@router.get("/edit")
async def plan_edit(request: Request, db: AsyncSession = Depends(get_db)):
    plan = await plan_service.get_plan(db)
    return request.app.state.templates.TemplateResponse(
        "plan/edit.html",
        {"request": request, "plan": plan},
    )


@router.post("/edit")
async def plan_update(
    request: Request,
    name: str = Form(""),
    description: str = Form(""),
    db: AsyncSession = Depends(get_db),
    _csrf: None = Depends(require_csrf),
):
    await plan_service.update_plan(db, name=name or None, description=description or None)
    return RedirectResponse(url="/plan?msg=Plan+updated", status_code=303)


@router.get("/rules/new")
async def rule_form(request: Request, layer: str = "CONTEXT"):
    return request.app.state.templates.TemplateResponse(
        "plan/rule_form.html",
        {
            "request": request,
            "rule": None,
            "layer": layer,
            "layers": PlanLayer,
            "rule_types": RuleType,
        },
    )


@router.post("/rules/new")
async def rule_create(
    request: Request,
    layer: str = Form(...),
    name: str = Form(...),
    description: str = Form(""),
    rule_type: str = Form("REQUIRED"),
    weight: int = Form(1),
    db: AsyncSession = Depends(get_db),
    _csrf: None = Depends(require_csrf),
):
    plan = await plan_service.get_plan(db)
    await plan_service.create_rule(
        db,
        plan.id,
        layer=layer,
        name=name,
        description=description or None,
        rule_type=rule_type,
        weight=weight,
    )
    return RedirectResponse(url=f"/plan?msg=Rule+added#{layer}", status_code=303)


@router.get("/rules/{rule_id}/edit")
async def rule_edit(request: Request, rule_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    rule = await plan_service.get_rule(db, rule_id)
    if not rule:
        return RedirectResponse(url="/plan?msg=Rule+not+found&msg_type=error", status_code=303)
    return request.app.state.templates.TemplateResponse(
        "plan/rule_form.html",
        {
            "request": request,
            "rule": rule,
            "layer": rule.layer,
            "layers": PlanLayer,
            "rule_types": RuleType,
        },
    )


@router.post("/rules/{rule_id}/edit")
async def rule_update(
    request: Request,
    rule_id: uuid.UUID,
    layer: str = Form(...),
    name: str = Form(...),
    description: str = Form(""),
    rule_type: str = Form("REQUIRED"),
    weight: int = Form(1),
    is_active: bool = Form(False),
    db: AsyncSession = Depends(get_db),
    _csrf: None = Depends(require_csrf),
):
    await plan_service.update_rule(
        db, rule_id,
        layer=layer, name=name, description=description or None,
        rule_type=rule_type, weight=weight, is_active=is_active,
    )
    return RedirectResponse(url=f"/plan?msg=Rule+updated#{layer}", status_code=303)


@router.post("/rules/{rule_id}/delete")
async def rule_delete(rule_id: uuid.UUID, db: AsyncSession = Depends(get_db), _csrf: None = Depends(require_csrf)):
    await plan_service.delete_rule(db, rule_id)
    return RedirectResponse(url="/plan?msg=Rule+deleted", status_code=303)
