import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.base import ErrorResponse, SuccessResponse
from app.schemas.checklist import ChecklistItemResponse, CheckToggleRequest
from app.schemas.ideas import (
    IdeaCreate,
    IdeaDetailResponse,
    IdeaResponse,
    IdeaUpdate,
    StateChangeRequest,
)
from app.services import checklist_service, idea_service, state_machine

router = APIRouter(prefix="/ideas", tags=["ideas"])


@router.get("", response_model=list[IdeaResponse])
async def list_ideas(
    active_only: bool = True,
    instrument: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    ideas = await idea_service.list_ideas(db, active_only=active_only, instrument=instrument)
    return [IdeaResponse.model_validate(i) for i in ideas]


@router.post("", response_model=IdeaResponse, status_code=201)
async def create_idea(body: IdeaCreate, db: AsyncSession = Depends(get_db)):
    idea = await idea_service.create_idea(
        db,
        instrument=body.instrument,
        direction=body.direction,
        risk_pct=body.risk_pct,
        notes=body.notes,
    )
    return IdeaResponse.model_validate(idea)


@router.get("/{idea_id}", response_model=IdeaDetailResponse)
async def get_idea(idea_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    idea = await idea_service.get_idea(db, idea_id)
    if idea is None:
        raise HTTPException(status_code=404, detail="Idea not found")

    pairs = await checklist_service.get_checks_with_rules(db, idea_id)
    layer_completion = await checklist_service.get_layer_completion(db, idea_id)
    actions = state_machine.get_available_actions(idea.state)

    checklist = [
        ChecklistItemResponse(
            id=check.id,
            rule_id=rule.id,
            rule_name=rule.name,
            rule_layer=rule.layer,
            rule_type=rule.rule_type,
            rule_weight=rule.weight,
            checked=check.checked,
            checked_at=check.checked_at,
            notes=check.notes,
        )
        for check, rule in pairs
    ]

    return IdeaDetailResponse(
        **IdeaResponse.model_validate(idea).model_dump(),
        checklist=checklist,
        layer_completion=layer_completion,
        available_actions=actions,
    )


@router.patch("/{idea_id}", response_model=IdeaResponse)
async def update_idea(
    idea_id: uuid.UUID,
    body: IdeaUpdate,
    db: AsyncSession = Depends(get_db),
):
    update_data = body.model_dump(exclude_unset=True)
    idea = await idea_service.update_idea(db, idea_id, **update_data)
    if idea is None:
        raise HTTPException(status_code=404, detail="Idea not found")
    return IdeaResponse.model_validate(idea)


@router.delete("/{idea_id}", response_model=SuccessResponse)
async def delete_idea(idea_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    deleted = await idea_service.delete_idea(db, idea_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Idea not found")
    return SuccessResponse(message="Idea deleted")


@router.get("/{idea_id}/checklist", response_model=list[ChecklistItemResponse])
async def get_checklist(idea_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    idea = await idea_service.get_idea(db, idea_id)
    if idea is None:
        raise HTTPException(status_code=404, detail="Idea not found")
    pairs = await checklist_service.get_checks_with_rules(db, idea_id)
    return [
        ChecklistItemResponse(
            id=check.id,
            rule_id=rule.id,
            rule_name=rule.name,
            rule_layer=rule.layer,
            rule_type=rule.rule_type,
            rule_weight=rule.weight,
            checked=check.checked,
            checked_at=check.checked_at,
            notes=check.notes,
        )
        for check, rule in pairs
    ]


@router.post("/{idea_id}/checks/{check_id}", response_model=ChecklistItemResponse)
async def toggle_check(
    idea_id: uuid.UUID,
    check_id: uuid.UUID,
    body: CheckToggleRequest,
    db: AsyncSession = Depends(get_db),
):
    idea = await idea_service.get_idea(db, idea_id)
    if idea is None:
        raise HTTPException(status_code=404, detail="Idea not found")

    check = await checklist_service.toggle_check(db, check_id, body.checked, notes=body.notes)
    if check is None:
        raise HTTPException(status_code=404, detail="Check not found")

    await checklist_service.update_idea_score(db, idea)

    # Fetch the associated rule for the response
    pairs = await checklist_service.get_checks_with_rules(db, idea_id)
    for c, r in pairs:
        if c.id == check_id:
            return ChecklistItemResponse(
                id=c.id,
                rule_id=r.id,
                rule_name=r.name,
                rule_layer=r.layer,
                rule_type=r.rule_type,
                rule_weight=r.weight,
                checked=c.checked,
                checked_at=c.checked_at,
                notes=c.notes,
            )
    raise HTTPException(status_code=404, detail="Check not found")


@router.post("/{idea_id}/advance", response_model=IdeaResponse)
async def advance_idea(
    idea_id: uuid.UUID,
    body: StateChangeRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    idea = await idea_service.get_idea(db, idea_id)
    if idea is None:
        raise HTTPException(status_code=404, detail="Idea not found")
    reason = body.reason if body else None
    try:
        idea = await state_machine.advance(db, idea, reason=reason)
    except state_machine.GuardError as e:
        raise HTTPException(
            status_code=409,
            detail={"code": "guard_error", "message": str(e), "errors": e.blockers},
        )
    except state_machine.TransitionError as e:
        raise HTTPException(
            status_code=409,
            detail={"code": "transition_error", "message": str(e)},
        )
    return IdeaResponse.model_validate(idea)


@router.post("/{idea_id}/regress", response_model=IdeaResponse)
async def regress_idea(
    idea_id: uuid.UUID,
    body: StateChangeRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    idea = await idea_service.get_idea(db, idea_id)
    if idea is None:
        raise HTTPException(status_code=404, detail="Idea not found")
    reason = body.reason if body else None
    try:
        idea = await state_machine.regress(db, idea, reason=reason)
    except state_machine.TransitionError as e:
        raise HTTPException(
            status_code=409,
            detail={"code": "transition_error", "message": str(e)},
        )
    return IdeaResponse.model_validate(idea)


@router.post("/{idea_id}/invalidate", response_model=IdeaResponse)
async def invalidate_idea(
    idea_id: uuid.UUID,
    body: StateChangeRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    idea = await idea_service.get_idea(db, idea_id)
    if idea is None:
        raise HTTPException(status_code=404, detail="Idea not found")
    reason = body.reason if body else None
    try:
        idea = await state_machine.invalidate(db, idea, reason=reason)
    except state_machine.TransitionError as e:
        raise HTTPException(
            status_code=409,
            detail={"code": "transition_error", "message": str(e)},
        )
    return IdeaResponse.model_validate(idea)
