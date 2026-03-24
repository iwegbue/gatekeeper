"""
Plan Review — JSON API router.

All routes are scoped to a specific plan: /api/v1/plans/{plan_id}/review/...
"""

import uuid
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.plan_review import PlanReviewDetailResponse, PlanReviewResponse
from app.services import plan_review_service
from app.services.ai.factory import AIConfigError, get_provider_from_db

if TYPE_CHECKING:
    from app.services.ai.base import AIProvider

router = APIRouter(prefix="/plans/{plan_id}/review", tags=["plan-review"])


async def _get_ai_provider(db: AsyncSession = Depends(get_db)) -> "AIProvider":
    try:
        return await get_provider_from_db(db)
    except AIConfigError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/run", response_model=PlanReviewDetailResponse, status_code=201)
async def run_review(
    plan_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    provider: "AIProvider" = Depends(_get_ai_provider),
):
    """
    Trigger a new plan review for the given plan.
    Fetches the last N completed journal entries, computes per-rule stats,
    calls the AI provider, and persists the resulting PlanReview.
    """
    review = await plan_review_service.run_plan_review(db, provider, plan_id)
    return PlanReviewDetailResponse.model_validate(review)


@router.get("/runs", response_model=list[PlanReviewResponse])
async def list_reviews(
    plan_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """List all plan reviews for the given plan, newest first."""
    reviews = await plan_review_service.list_plan_reviews(db, plan_id)
    return [PlanReviewResponse.model_validate(r) for r in reviews]


@router.get("/runs/{review_id}", response_model=PlanReviewDetailResponse)
async def get_review(
    plan_id: uuid.UUID,
    review_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a single plan review with its full report."""
    review = await plan_review_service.get_plan_review(db, review_id)
    if review is None or review.plan_id != plan_id:
        raise HTTPException(status_code=404, detail="Plan review not found")
    return PlanReviewDetailResponse.model_validate(review)
