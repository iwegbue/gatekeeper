import uuid

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import RedirectResponse

from app.csrf import require_csrf
from app.database import get_db
from app.models.enums import PlanLayer, RuleType
from app.services import plan_service
from app.services.plan_templates import get_template, list_templates

router = APIRouter(prefix="/plan")


# ── Plan list ─────────────────────────────────────────────────────────────────


@router.get("")
async def plan_list(request: Request, db: AsyncSession = Depends(get_db)):
    plans = await plan_service.list_plans(db)
    if not plans:
        plan = await plan_service.get_active_plan(db)
        plans = [plan]
    return request.app.state.templates.TemplateResponse(
        "plan/list.html",
        {"request": request, "plans": plans},
    )


@router.get("/templates")
async def plan_templates_gallery(
    request: Request,
    mode: str = "new",
    plan_id: str = "",
):
    return request.app.state.templates.TemplateResponse(
        "plan/templates.html",
        {
            "request": request,
            "templates": list_templates(),
            "mode": mode,
            "plan_id": plan_id,
        },
    )


@router.get("/new")
async def plan_new(request: Request):
    return request.app.state.templates.TemplateResponse(
        "plan/new.html",
        {"request": request},
    )


@router.post("/new")
async def plan_create(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    template_id: str = Form("scratch"),
    activate: bool = Form(False),
    db: AsyncSession = Depends(get_db),
    _csrf: None = Depends(require_csrf),
):
    effective_template_id = template_id if (template_id and template_id != "scratch") else None
    plan = await plan_service.create_plan(
        db, name=name, description=description or None,
        template_id=effective_template_id, activate=activate,
    )

    if effective_template_id:
        tmpl = get_template(effective_template_id)
        if tmpl:
            for rule in tmpl["rules"]:
                await plan_service.create_rule(
                    db,
                    plan.id,
                    layer=rule["layer"],
                    name=rule["name"],
                    description=rule.get("description"),
                    rule_type=rule["rule_type"],
                    weight=rule["weight"],
                    _track_modification=False,
                )

    return RedirectResponse(url=f"/plan/{plan.id}?msg=Plan+created", status_code=303)


@router.post("/{plan_id}/activate")
async def plan_activate(
    plan_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _csrf: None = Depends(require_csrf),
):
    result = await plan_service.activate_plan(db, plan_id)
    if result is None:
        return RedirectResponse(url="/plan?msg=Plan+not+found&msg_type=error", status_code=303)
    return RedirectResponse(url="/plan?msg=Plan+activated", status_code=303)


@router.post("/{plan_id}/delete")
async def plan_delete(
    plan_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _csrf: None = Depends(require_csrf),
):
    error = await plan_service.delete_plan(db, plan_id)
    if error == "active":
        return RedirectResponse(url="/plan?msg=Cannot+delete+the+active+plan&msg_type=error", status_code=303)
    if error == "has_ideas":
        return RedirectResponse(
            url="/plan?msg=Cannot+delete+a+plan+that+has+ideas&msg_type=error", status_code=303
        )
    return RedirectResponse(url="/plan?msg=Plan+deleted", status_code=303)


@router.post("/{plan_id}/duplicate")
async def plan_duplicate(
    plan_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _csrf: None = Depends(require_csrf),
):
    new_plan = await plan_service.duplicate_plan(db, plan_id)
    if new_plan is None:
        return RedirectResponse(url="/plan?msg=Plan+not+found&msg_type=error", status_code=303)
    return RedirectResponse(url=f"/plan/{new_plan.id}?msg=Plan+duplicated", status_code=303)


# ── Plan detail (view/edit a specific plan) ──────────────────────────────────


@router.get("/{plan_id}")
async def plan_detail(request: Request, plan_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    plan = await plan_service.get_plan_by_id(db, plan_id)
    if plan is None:
        return RedirectResponse(url="/plan?msg=Plan+not+found&msg_type=error", status_code=303)
    rules_by_layer = await plan_service.get_rules_by_layer(db, plan.id)
    total_rules = sum(len(v) for v in rules_by_layer.values())
    return request.app.state.templates.TemplateResponse(
        "plan/index.html",
        {
            "request": request,
            "plan": plan,
            "rules_by_layer": rules_by_layer,
            "total_rules": total_rules,
            "layers": PlanLayer,
            "rule_types": RuleType,
            "plan_id_str": str(plan.id),
        },
    )


@router.get("/{plan_id}/edit")
async def plan_edit(request: Request, plan_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    plan = await plan_service.get_plan_by_id(db, plan_id)
    if plan is None:
        return RedirectResponse(url="/plan?msg=Plan+not+found&msg_type=error", status_code=303)
    return request.app.state.templates.TemplateResponse(
        "plan/edit.html",
        {"request": request, "plan": plan},
    )


@router.post("/{plan_id}/edit")
async def plan_update(
    request: Request,
    plan_id: uuid.UUID,
    name: str = Form(""),
    description: str = Form(""),
    db: AsyncSession = Depends(get_db),
    _csrf: None = Depends(require_csrf),
):
    result = await plan_service.update_plan(db, plan_id=plan_id, name=name or None, description=description or None)
    if result is None:
        return RedirectResponse(url="/plan?msg=Plan+not+found&msg_type=error", status_code=303)
    return RedirectResponse(url=f"/plan/{plan_id}?msg=Plan+updated", status_code=303)


# ── Rules ─────────────────────────────────────────────────────────────────────


@router.get("/{plan_id}/rules/new")
async def rule_form(request: Request, plan_id: uuid.UUID, layer: str = "CONTEXT", db: AsyncSession = Depends(get_db)):
    plan = await plan_service.get_plan_by_id(db, plan_id)
    if plan is None:
        return RedirectResponse(url="/plan?msg=Plan+not+found&msg_type=error", status_code=303)
    return request.app.state.templates.TemplateResponse(
        "plan/rule_form.html",
        {
            "request": request,
            "plan": plan,
            "rule": None,
            "layer": layer,
            "layers": PlanLayer,
            "rule_types": RuleType,
        },
    )


@router.post("/{plan_id}/rules/new")
async def rule_create(
    request: Request,
    plan_id: uuid.UUID,
    layer: str = Form(...),
    name: str = Form(...),
    description: str = Form(""),
    rule_type: str = Form("REQUIRED"),
    weight: int = Form(1),
    db: AsyncSession = Depends(get_db),
    _csrf: None = Depends(require_csrf),
):
    await plan_service.create_rule(
        db,
        plan_id,
        layer=layer,
        name=name,
        description=description or None,
        rule_type=rule_type,
        weight=weight,
    )
    return RedirectResponse(url=f"/plan/{plan_id}?msg=Rule+added#{layer}", status_code=303)


@router.get("/{plan_id}/rules/{rule_id}/edit")
async def rule_edit(
    request: Request, plan_id: uuid.UUID, rule_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    plan = await plan_service.get_plan_by_id(db, plan_id)
    rule = await plan_service.get_rule_for_plan(db, rule_id, plan_id)
    if not plan or not rule:
        return RedirectResponse(url=f"/plan/{plan_id}?msg=Rule+not+found&msg_type=error", status_code=303)
    return request.app.state.templates.TemplateResponse(
        "plan/rule_form.html",
        {
            "request": request,
            "plan": plan,
            "rule": rule,
            "layer": rule.layer,
            "layers": PlanLayer,
            "rule_types": RuleType,
        },
    )


@router.post("/{plan_id}/rules/{rule_id}/edit")
async def rule_update(
    request: Request,
    plan_id: uuid.UUID,
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
    rule = await plan_service.get_rule_for_plan(db, rule_id, plan_id)
    if rule is None:
        return RedirectResponse(url=f"/plan/{plan_id}?msg=Rule+not+found&msg_type=error", status_code=303)
    await plan_service.update_rule(
        db,
        rule_id,
        layer=layer,
        name=name,
        description=description or None,
        rule_type=rule_type,
        weight=weight,
        is_active=is_active,
    )
    return RedirectResponse(url=f"/plan/{plan_id}?msg=Rule+updated#{layer}", status_code=303)


@router.post("/{plan_id}/rules/{rule_id}/delete")
async def rule_delete(
    plan_id: uuid.UUID,
    rule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _csrf: None = Depends(require_csrf),
):
    rule = await plan_service.get_rule_for_plan(db, rule_id, plan_id)
    if rule is None:
        return RedirectResponse(url=f"/plan/{plan_id}?msg=Rule+not+found&msg_type=error", status_code=303)
    await plan_service.delete_rule(db, rule_id)
    return RedirectResponse(url=f"/plan/{plan_id}?msg=Rule+deleted", status_code=303)


# ── Reset ─────────────────────────────────────────────────────────────────────


@router.get("/{plan_id}/reset")
async def plan_reset_confirm(
    request: Request,
    plan_id: uuid.UUID,
    preselect: str = "",
    db: AsyncSession = Depends(get_db),
):
    plan = await plan_service.get_plan_by_id(db, plan_id)
    if plan is None:
        return RedirectResponse(url="/plan?msg=Plan+not+found&msg_type=error", status_code=303)
    rules_by_layer = await plan_service.get_rules_by_layer(db, plan.id, active_only=False)
    total_rules = sum(len(v) for v in rules_by_layer.values())
    return request.app.state.templates.TemplateResponse(
        "plan/reset.html",
        {
            "request": request,
            "plan": plan,
            "total_rules": total_rules,
            "templates": list_templates(),
            "preselect": preselect,
        },
    )


@router.post("/{plan_id}/reset")
async def plan_reset(
    request: Request,
    plan_id: uuid.UUID,
    template_id: str = Form("scratch"),
    plan_name: str = Form(""),
    plan_description: str = Form(""),
    db: AsyncSession = Depends(get_db),
    _csrf: None = Depends(require_csrf),
):
    plan = await plan_service.get_plan_by_id(db, plan_id)
    if plan is None:
        return RedirectResponse(url="/plan?msg=Plan+not+found&msg_type=error", status_code=303)

    await plan_service.clear_rules(db, plan.id)

    effective_template_id = template_id if (template_id and template_id != "scratch") else None
    await plan_service.update_plan(
        db,
        plan_id=plan.id,
        name=plan_name or None,
        description=plan_description or None,
        template_id=effective_template_id,
    )

    if effective_template_id:
        tmpl = get_template(effective_template_id)
        if tmpl:
            for rule in tmpl["rules"]:
                await plan_service.create_rule(
                    db,
                    plan.id,
                    layer=rule["layer"],
                    name=rule["name"],
                    description=rule.get("description"),
                    rule_type=rule["rule_type"],
                    weight=rule["weight"],
                    _track_modification=False,
                )

    return RedirectResponse(url=f"/plan/{plan_id}?msg=Plan+reset+successfully", status_code=303)
