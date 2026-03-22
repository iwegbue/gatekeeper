"""
Plan Builder — AI-powered multi-turn wizard for creating trading plan rules.
"""

import json
import logging
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse, RedirectResponse

from app.database import get_db
from app.services import ai_service
from app.services import instrument_service
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
    def redirect(msg: str, msg_type: str = "success") -> RedirectResponse:
        return RedirectResponse(
            f"/plan?msg={quote(msg)}&msg_type={msg_type}",
            status_code=303,
        )

    session = await pb_service.get_session(db)
    if not session or not session.conversation:
        return redirect("No conversation found — start the Plan Builder first", "warning")

    try:
        provider = await ai_factory.get_provider_from_db(db)
    except ai_factory.AIConfigError as e:
        return redirect(str(e), "error")

    try:
        rules = await ai_service.extract_rules_from_conversation(db, provider, session.conversation)
        instruments = await ai_service.extract_instruments_from_conversation(db, provider, session.conversation)
        await db.commit()  # persist both AIAnalysis log records
    except Exception:
        logger.exception("Plan Builder extraction failed")
        await db.rollback()
        return redirect("Could not extract plan data — add rules manually from the conversation", "error")

    if not rules and not instruments:
        return redirect("No rules could be extracted — the conversation may need a summary first", "warning")

    plan = await plan_service.get_active_plan(db)
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

    new_instrument_count = 0
    for inst in instruments:
        existing = await instrument_service.get_by_symbol(db, inst["symbol"])
        if existing is None:
            await instrument_service.create(
                db,
                symbol=inst["symbol"],
                display_name=inst["display_name"],
                asset_class=inst["asset_class"],
            )
            new_instrument_count += 1

    await db.commit()

    parts = []
    if rules:
        parts.append(f"{len(rules)} rule{'s' if len(rules) != 1 else ''}")
    if new_instrument_count:
        parts.append(f"{new_instrument_count} instrument{'s' if new_instrument_count != 1 else ''}")
    return redirect(f"{' and '.join(parts)} added from Plan Builder")


@router.post("/clear")
async def builder_clear(request: Request, db: AsyncSession = Depends(get_db)):
    """Wipe the saved conversation and return to the suggestion panel."""
    await pb_service.clear_session(db)
    await db.commit()
    return RedirectResponse("/plan/builder", status_code=303)
