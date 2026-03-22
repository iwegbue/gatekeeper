"""
Plan Builder — AI-powered multi-turn wizard for creating trading plan rules.
"""

import json
import logging

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse, RedirectResponse

from app.database import get_db
from app.services import ai_service
from app.services import plan_builder_service as pb_service
from app.services.ai import factory as ai_factory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/plan/builder")


@router.get("")
async def builder_index(request: Request, db: AsyncSession = Depends(get_db)):
    session = await pb_service.get_or_create_session(db)
    await db.commit()
    return request.app.state.templates.TemplateResponse(
        "plan/builder.html",
        {
            "request": request,
            "saved_history": pb_service.conversation_to_json(session),
            "has_history": len(session.conversation) > 0,
        },
    )


@router.post("/chat")
async def builder_chat(
    request: Request,
    message: str = Form(...),
    history: str = Form("[]"),
    db: AsyncSession = Depends(get_db),
):
    """Accepts a user message, returns AI response as JSON, persists the turn."""
    try:
        provider = await ai_factory.get_provider_from_db(db)
    except ai_factory.AIConfigError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    try:
        conversation = json.loads(history)
    except (json.JSONDecodeError, ValueError):
        conversation = []

    conversation.append({"role": "user", "content": message})

    try:
        response = await ai_service.plan_builder_chat(db, provider, conversation)
        await pb_service.append_turns(db, message, response)
        await db.commit()
        conversation.append({"role": "assistant", "content": response})
        return JSONResponse(
            {
                "response": response,
                "history": json.dumps(conversation),
            }
        )
    except Exception:
        logger.exception("AI plan builder error")
        await db.rollback()
        return JSONResponse({"error": "AI request failed. Please try again."}, status_code=500)


@router.post("/clear")
async def builder_clear(request: Request, db: AsyncSession = Depends(get_db)):
    """Wipe the saved conversation and return to the suggestion panel."""
    await pb_service.clear_session(db)
    await db.commit()
    return RedirectResponse("/plan/builder", status_code=303)
