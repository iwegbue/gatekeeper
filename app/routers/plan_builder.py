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
from app.services import plan_service
from app.services.plan_builder_service import LAYERS
from app.services.ai import factory as ai_factory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/plan/builder")


@router.get("")
async def builder_index(request: Request, db: AsyncSession = Depends(get_db)):
    session = await pb_service.get_or_create_session(db)
    await db.commit()
    covered = pb_service.covered_layers(session.conversation)
    return request.app.state.templates.TemplateResponse(
        "plan/builder.html",
        {
            "request": request,
            "saved_history": pb_service.conversation_to_json(session),
            "has_history": len(session.conversation) > 0,
            "layers": LAYERS,
            "covered_layers": covered,
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
        covered = pb_service.covered_layers(conversation)
        return JSONResponse(
            {
                "response": response,
                "history": json.dumps(conversation),
                "covered_layers": covered,
            }
        )
    except Exception:
        logger.exception("AI plan builder error")
        await db.rollback()
        return JSONResponse({"error": "AI request failed. Please try again."}, status_code=500)


@router.post("/done")
async def builder_done(request: Request, db: AsyncSession = Depends(get_db)):
    """Extract rules from the saved conversation and write them to the trading plan."""
    session = await pb_service.get_session(db)
    if not session or not session.conversation:
        return RedirectResponse(
            "/plan?msg=No conversation found — start the Plan Builder first&msg_type=warning",
            status_code=303,
        )

    try:
        provider = await ai_factory.get_provider_from_db(db)
    except ai_factory.AIConfigError as e:
        return RedirectResponse(
            f"/plan?msg={e}&msg_type=error",
            status_code=303,
        )

    try:
        rules = await ai_service.extract_rules_from_conversation(db, provider, session.conversation)
    except Exception:
        logger.exception("Rule extraction failed")
        await db.rollback()
        return RedirectResponse(
            "/plan?msg=Could not extract rules — add them manually from the conversation&msg_type=error",
            status_code=303,
        )

    if not rules:
        return RedirectResponse(
            "/plan?msg=No rules could be extracted — the conversation may need a summary first&msg_type=warning",
            status_code=303,
        )

    plan = await plan_service.get_plan(db)
    for rule in rules:
        await plan_service.create_rule(
            db,
            plan.id,
            layer=rule["layer"],
            name=rule["name"],
            description=rule["description"],
            rule_type=rule["rule_type"],
            weight=rule["weight"],
        )

    await db.commit()
    count = len(rules)
    return RedirectResponse(
        f"/plan?msg={count} rule{'s' if count != 1 else ''} added from Plan Builder&msg_type=success",
        status_code=303,
    )


@router.post("/clear")
async def builder_clear(request: Request, db: AsyncSession = Depends(get_db)):
    """Wipe the saved conversation and return to the suggestion panel."""
    await pb_service.clear_session(db)
    await db.commit()
    return RedirectResponse("/plan/builder", status_code=303)
