"""
Plan Builder session service — persists multi-turn conversation to the DB.

Single-user app: one active session keyed by SESSION_KEY.
The session survives page refreshes and browser closes.
"""

import json
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.plan_builder_session import PlanBuilderSession

logger = logging.getLogger(__name__)

SESSION_KEY = "default"


async def get_session(db: AsyncSession) -> PlanBuilderSession | None:
    result = await db.execute(
        select(PlanBuilderSession).where(PlanBuilderSession.session_key == SESSION_KEY)
    )
    return result.scalar_one_or_none()


async def get_or_create_session(db: AsyncSession) -> PlanBuilderSession:
    session = await get_session(db)
    if session is None:
        session = PlanBuilderSession(session_key=SESSION_KEY, conversation=[])
        db.add(session)
        await db.flush()
    return session


async def append_turns(
    db: AsyncSession,
    user_message: str,
    assistant_response: str,
) -> PlanBuilderSession:
    """Append a user+assistant turn pair and persist."""
    session = await get_or_create_session(db)
    updated = list(session.conversation)
    updated.append({"role": "user", "content": user_message})
    updated.append({"role": "assistant", "content": assistant_response})
    session.conversation = updated
    await db.flush()
    return session


async def clear_session(db: AsyncSession) -> None:
    """Wipe the conversation so the user can start fresh."""
    session = await get_session(db)
    if session is not None:
        session.conversation = []
        await db.flush()


def conversation_to_json(session: PlanBuilderSession) -> str:
    return json.dumps(session.conversation)


# Layer names in display order — matches the 7-layer state machine.
LAYERS = ["CONTEXT", "SETUP", "CONFIRMATION", "ENTRY", "RISK", "MANAGEMENT", "BEHAVIORAL"]


def covered_layers(conversation: list[dict]) -> list[str]:
    """
    Return the set of layers mentioned in assistant messages so far.
    A layer is considered 'covered' once the assistant has explicitly
    named it — which the system prompt instructs it to do when moving
    to each new layer.
    """
    mentioned: set[str] = set()
    for turn in conversation:
        if turn.get("role") == "assistant":
            text = turn.get("content", "").upper()
            for layer in LAYERS:
                if layer in text:
                    mentioned.add(layer)
    return [l for l in LAYERS if l in mentioned]
