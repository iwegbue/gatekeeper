"""
Plan Builder — AI-powered multi-turn wizard for creating trading plan rules.
"""
from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse

from app.database import get_db
from app.services.ai import factory as ai_factory
from app.services import ai_service

router = APIRouter(prefix="/plan/builder")


@router.get("")
async def builder_index(request: Request):
    return request.app.state.templates.TemplateResponse(
        "plan/builder.html",
        {"request": request},
    )


@router.post("/chat")
async def builder_chat(
    request: Request,
    message: str = Form(...),
    history: str = Form("[]"),  # JSON-encoded conversation history
    db: AsyncSession = Depends(get_db),
):
    """HTMX endpoint: accepts a user message, returns AI response as JSON."""
    import json

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
        await db.commit()
        conversation.append({"role": "assistant", "content": response})
        return JSONResponse({
            "response": response,
            "history": json.dumps(conversation),
        })
    except Exception as e:
        await db.rollback()
        return JSONResponse({"error": f"AI error: {str(e)}"}, status_code=500)
