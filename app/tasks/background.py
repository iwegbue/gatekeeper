"""
Background tasks — entry window expiry, journal reminders.
"""

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app.database import AsyncSessionFactory
from app.models.enums import IdeaState
from app.models.idea import Idea
from app.services import notification_service, state_machine

logger = logging.getLogger(__name__)


async def check_expired_entry_windows() -> None:
    """Invalidate ideas whose entry window has expired."""
    if AsyncSessionFactory is None:
        return
    try:
        async with AsyncSessionFactory() as db:
            now = datetime.now(timezone.utc)
            result = await db.execute(
                select(Idea).where(
                    Idea.entry_window_expires_at <= now,
                    Idea.state == IdeaState.ENTRY_PERMITTED.value,
                )
            )
            expired = list(result.scalars().all())
            for idea in expired:
                try:
                    await state_machine.invalidate(db, idea, reason="Entry window expired")
                    await notification_service.notify_idea_expired(db, idea.instrument, idea.direction)
                    logger.info("Invalidated expired idea: %s %s", idea.instrument, idea.direction)
                except Exception as e:
                    logger.error("Error invalidating idea %s: %s", idea.id, e)
            if expired:
                await db.commit()
    except Exception as e:
        logger.error("Error in check_expired_entry_windows: %s", e)


async def _run_loop(coro_func, interval_seconds: int) -> None:
    while True:
        try:
            await coro_func()
        except Exception as e:
            logger.error("Background task error: %s", e)
        await asyncio.sleep(interval_seconds)


def start_background_tasks(app) -> None:
    """Start all background loops. Called from app lifespan."""
    import asyncio

    loop = asyncio.get_event_loop()
    loop.create_task(_run_loop(check_expired_entry_windows, interval_seconds=300))
    logger.info("Background tasks started")
