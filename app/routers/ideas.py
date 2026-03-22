import uuid

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import RedirectResponse

from app.csrf import require_csrf
from app.database import get_db
from app.models.enums import Direction, IdeaState
from app.services import checklist_service, idea_service, plan_service, state_machine

router = APIRouter(prefix="/ideas")


@router.get("")
async def idea_list(request: Request, db: AsyncSession = Depends(get_db)):
    show_all = request.query_params.get("all") == "1"
    ideas = await idea_service.list_ideas(db, active_only=not show_all)
    return request.app.state.templates.TemplateResponse(
        "ideas/list.html",
        {
            "request": request,
            "ideas": ideas,
            "show_all": show_all,
        },
    )


@router.get("/new")
async def idea_new(request: Request, db: AsyncSession = Depends(get_db)):
    plan = await plan_service.get_active_plan(db)
    has_rules = bool(await plan_service.get_rules_by_layer(db, plan.id))
    return request.app.state.templates.TemplateResponse(
        "ideas/create.html",
        {
            "request": request,
            "directions": Direction,
            "has_rules": has_rules,
        },
    )


@router.post("/new")
async def idea_create(
    instrument: str = Form(...),
    direction: str = Form(...),
    risk_pct: float | None = Form(None),
    notes: str = Form(""),
    db: AsyncSession = Depends(get_db),
    _csrf: None = Depends(require_csrf),
):
    idea = await idea_service.create_idea(
        db,
        instrument=instrument,
        direction=direction,
        risk_pct=risk_pct,
        notes=notes or None,
    )
    await db.commit()
    return RedirectResponse(url=f"/ideas/{idea.id}", status_code=303)


@router.get("/{idea_id}")
async def idea_detail(request: Request, idea_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    idea = await idea_service.get_idea(db, idea_id)
    if idea is None:
        return RedirectResponse(url="/ideas?msg=Idea+not+found&msg_type=error", status_code=303)

    pairs = await checklist_service.get_checks_with_rules(db, idea_id)
    layer_completion = await checklist_service.get_layer_completion(db, idea_id)
    checked_score, total_score = await checklist_service.compute_score(db, idea_id)
    grade = await checklist_service.compute_grade(db, idea_id)
    actions = state_machine.get_available_actions(idea.state)

    # Group checks by layer
    from collections import defaultdict

    checks_by_layer: dict = defaultdict(list)
    for check, rule in pairs:
        checks_by_layer[rule.layer].append((check, rule))

    from app.models.enums import PlanLayer

    return request.app.state.templates.TemplateResponse(
        "ideas/detail.html",
        {
            "request": request,
            "idea": idea,
            "checks_by_layer": dict(checks_by_layer),
            "layer_completion": layer_completion,
            "checked_score": checked_score,
            "total_score": total_score,
            "grade": grade,
            "actions": actions,
            "layers": PlanLayer,
            "states": IdeaState,
        },
    )


@router.post("/{idea_id}/edit")
async def idea_edit(
    idea_id: uuid.UUID,
    notes: str = Form(""),
    risk_pct: float | None = Form(None),
    db: AsyncSession = Depends(get_db),
    _csrf: None = Depends(require_csrf),
):
    await idea_service.update_idea(db, idea_id, notes=notes or None, risk_pct=risk_pct)
    await db.commit()
    return RedirectResponse(url=f"/ideas/{idea_id}?msg=Updated", status_code=303)


@router.post("/{idea_id}/delete")
async def idea_delete(idea_id: uuid.UUID, db: AsyncSession = Depends(get_db), _csrf: None = Depends(require_csrf)):
    await idea_service.delete_idea(db, idea_id)
    await db.commit()
    return RedirectResponse(url="/ideas?msg=Idea+deleted", status_code=303)


# ── Checklist ─────────────────────────────────────────────────────────────────


@router.post("/{idea_id}/checks/{check_id}/toggle")
async def check_toggle(
    request: Request,
    idea_id: uuid.UUID,
    check_id: uuid.UUID,
    checked: bool = Form(False),
    notes: str = Form(""),
    db: AsyncSession = Depends(get_db),
    _csrf: None = Depends(require_csrf),
):
    await checklist_service.toggle_check(db, check_id, checked, notes=notes or None)
    idea = await idea_service.get_idea(db, idea_id)
    if idea:
        await checklist_service.update_idea_score(db, idea)
    await db.commit()

    # HTMX partial — return updated checklist block
    pairs = await checklist_service.get_checks_with_rules(db, idea_id)
    layer_completion = await checklist_service.get_layer_completion(db, idea_id)
    checked_score, total_score = await checklist_service.compute_score(db, idea_id)
    grade = await checklist_service.compute_grade(db, idea_id)
    actions = state_machine.get_available_actions(idea.state) if idea else {}

    from collections import defaultdict

    checks_by_layer: dict = defaultdict(list)
    for check, rule in pairs:
        checks_by_layer[rule.layer].append((check, rule))

    from app.models.enums import PlanLayer

    return request.app.state.templates.TemplateResponse(
        "ideas/_checklist.html",
        {
            "request": request,
            "idea": idea,
            "checks_by_layer": dict(checks_by_layer),
            "layer_completion": layer_completion,
            "checked_score": checked_score,
            "total_score": total_score,
            "grade": grade,
            "actions": actions,
            "layers": PlanLayer,
        },
    )


# ── State transitions ──────────────────────────────────────────────────────────


@router.post("/{idea_id}/advance")
async def idea_advance(
    idea_id: uuid.UUID,
    reason: str = Form(""),
    db: AsyncSession = Depends(get_db),
    _csrf: None = Depends(require_csrf),
):
    idea = await idea_service.get_idea(db, idea_id)
    if idea is None:
        return RedirectResponse(url="/ideas?msg=Idea+not+found&msg_type=error", status_code=303)
    try:
        await state_machine.advance(db, idea, reason=reason or None)
        await db.commit()
        return RedirectResponse(url=f"/ideas/{idea_id}?msg=Advanced+to+{idea.state}", status_code=303)
    except state_machine.GuardError as e:
        blockers = ", ".join(e.blockers)
        await db.rollback()
        return RedirectResponse(
            url=f"/ideas/{idea_id}?msg=Blocked+by%3A+{blockers}&msg_type=error",
            status_code=303,
        )
    except state_machine.TransitionError as e:
        await db.rollback()
        return RedirectResponse(
            url=f"/ideas/{idea_id}?msg={str(e)}&msg_type=error",
            status_code=303,
        )


@router.post("/{idea_id}/regress")
async def idea_regress(
    idea_id: uuid.UUID,
    reason: str = Form(""),
    db: AsyncSession = Depends(get_db),
    _csrf: None = Depends(require_csrf),
):
    idea = await idea_service.get_idea(db, idea_id)
    if idea is None:
        return RedirectResponse(url="/ideas?msg=Idea+not+found&msg_type=error", status_code=303)
    try:
        await state_machine.regress(db, idea, reason=reason or None)
        await db.commit()
        return RedirectResponse(url=f"/ideas/{idea_id}?msg=Regressed", status_code=303)
    except state_machine.TransitionError as e:
        await db.rollback()
        return RedirectResponse(
            url=f"/ideas/{idea_id}?msg={str(e)}&msg_type=error",
            status_code=303,
        )


@router.post("/{idea_id}/invalidate")
async def idea_invalidate(
    idea_id: uuid.UUID,
    reason: str = Form(""),
    db: AsyncSession = Depends(get_db),
    _csrf: None = Depends(require_csrf),
):
    idea = await idea_service.get_idea(db, idea_id)
    if idea is None:
        return RedirectResponse(url="/ideas?msg=Idea+not+found&msg_type=error", status_code=303)
    try:
        await state_machine.invalidate(db, idea, reason=reason or None)
        await db.commit()
        return RedirectResponse(url=f"/ideas/{idea_id}?msg=Invalidated", status_code=303)
    except state_machine.TransitionError as e:
        await db.rollback()
        return RedirectResponse(
            url=f"/ideas/{idea_id}?msg={str(e)}&msg_type=error",
            status_code=303,
        )
