"""
Idea CRUD service.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import IdeaState
from app.models.idea import Idea
from app.services import checklist_service, plan_service, settings_service


async def get_idea(db: AsyncSession, idea_id: uuid.UUID) -> Idea | None:
    result = await db.execute(select(Idea).where(Idea.id == idea_id))
    return result.scalar_one_or_none()


async def list_ideas(
    db: AsyncSession,
    *,
    active_only: bool = False,
    instrument: str | None = None,
) -> list[Idea]:
    stmt = select(Idea).order_by(Idea.created_at.desc())
    if active_only:
        terminal = [IdeaState.CLOSED.value, IdeaState.INVALIDATED.value]
        stmt = stmt.where(Idea.state.not_in(terminal))
    if instrument:
        stmt = stmt.where(Idea.instrument == instrument.upper())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create_idea(
    db: AsyncSession,
    *,
    instrument: str,
    direction: str,
    risk_pct: float | None = None,
    notes: str | None = None,
    plan_id: uuid.UUID | None = None,
) -> Idea:
    idea = Idea(
        instrument=instrument.upper().strip(),
        direction=direction,
        state=IdeaState.WATCHING.value,
        risk_pct=risk_pct,
        notes=notes,
    )
    db.add(idea)
    await db.flush()

    # Set entry window expiry from settings
    s = await settings_service.get_settings(db)
    idea.entry_window_expires_at = datetime.now(timezone.utc) + timedelta(hours=s.entry_window_hours)

    # Initialize checklist if plan_id provided
    if plan_id is None:
        plan = await plan_service.get_plan(db)
        plan_id = plan.id
    await checklist_service.initialize_checks(db, idea.id, plan_id)

    await db.flush()
    return idea


async def update_idea(
    db: AsyncSession,
    idea_id: uuid.UUID,
    **kwargs,
) -> Idea | None:
    idea = await get_idea(db, idea_id)
    if idea is None:
        return None
    for key, value in kwargs.items():
        if hasattr(idea, key) and key not in ("id", "state"):
            setattr(idea, key, value)
    await db.flush()
    return idea


async def delete_idea(db: AsyncSession, idea_id: uuid.UUID) -> bool:
    idea = await get_idea(db, idea_id)
    if idea is None:
        return False
    await db.delete(idea)
    await db.flush()
    return True
