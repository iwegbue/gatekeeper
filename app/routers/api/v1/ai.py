import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.ai import AIReviewResponse, RuleClarityRequest
from app.services import ai_service
from app.services.ai.factory import AIConfigError, get_provider_from_db

router = APIRouter(prefix="/ai", tags=["ai"])


async def _get_provider(db: AsyncSession):
    try:
        return await get_provider_from_db(db)
    except AIConfigError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/idea-review/{idea_id}", response_model=AIReviewResponse)
async def idea_review(idea_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    provider = await _get_provider(db)
    content = await ai_service.idea_review(db, provider, idea_id)
    return AIReviewResponse(content=content)


@router.post("/journal-coach/{entry_id}", response_model=AIReviewResponse)
async def journal_coach(entry_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    provider = await _get_provider(db)
    content = await ai_service.journal_coach(db, provider, entry_id)
    return AIReviewResponse(content=content)


@router.post("/rule-clarity", response_model=AIReviewResponse)
async def rule_clarity(body: RuleClarityRequest, db: AsyncSession = Depends(get_db)):
    provider = await _get_provider(db)
    content = await ai_service.rule_clarity_check(
        db,
        provider,
        body.rule_name,
        body.rule_description,
        body.layer,
    )
    return AIReviewResponse(content=content)
