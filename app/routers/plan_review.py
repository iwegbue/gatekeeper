"""
Plan Review — HTML router.

Routes are scoped to a specific plan (/plan/{plan_id}/review/*).
"""

import logging
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.csrf import require_csrf
from app.database import get_db
from app.services import plan_service
from app.services.ai.factory import AIConfigError, get_provider_from_db
from app.services import plan_review_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/plan/{plan_id}/review")


@router.get("")
async def plan_review_index(
    request: Request,
    plan_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    plan = await plan_service.get_plan_by_id(db, plan_id)
    if plan is None:
        return RedirectResponse(url="/plan?msg=Plan+not+found&msg_type=error", status_code=303)

    eligibility = await plan_review_service.get_review_eligibility(db, plan_id)
    reviews = await plan_review_service.list_plan_reviews(db, plan_id)

    return request.app.state.templates.TemplateResponse(
        "plan_review/index.html",
        {
            "request": request,
            "plan": plan,
            "eligibility": eligibility,
            "reviews": reviews,
        },
    )


@router.post("/run")
async def plan_review_run(
    request: Request,
    plan_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _csrf: None = Depends(require_csrf),
):
    plan = await plan_service.get_plan_by_id(db, plan_id)
    if plan is None:
        return RedirectResponse(url="/plan?msg=Plan+not+found&msg_type=error", status_code=303)

    try:
        provider = await get_provider_from_db(db)
    except AIConfigError:
        return RedirectResponse(
            f"/plan/{plan_id}/review?msg=AI+provider+not+configured.+Configure+it+in+Settings.&msg_type=error",
            status_code=303,
        )

    try:
        review = await plan_review_service.run_plan_review(db, provider, plan_id)
    except Exception as exc:
        logger.exception("Plan review failed for plan %s: %s", plan_id, exc)
        return RedirectResponse(
            f"/plan/{plan_id}/review?msg=Review+failed.+Check+your+AI+provider+settings.&msg_type=error",
            status_code=303,
        )

    if review.status == "FAILED":
        return RedirectResponse(
            f"/plan/{plan_id}/review?msg=Review+failed:+{review.error_message or 'unknown+error'}&msg_type=error",
            status_code=303,
        )

    return RedirectResponse(f"/plan/{plan_id}/review/{review.id}", status_code=303)


@router.get("/{review_id}")
async def plan_review_detail(
    request: Request,
    plan_id: uuid.UUID,
    review_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    plan = await plan_service.get_plan_by_id(db, plan_id)
    if plan is None:
        return RedirectResponse(url="/plan?msg=Plan+not+found&msg_type=error", status_code=303)

    review = await plan_review_service.get_plan_review(db, review_id)
    if review is None or review.plan_id != plan_id:
        return RedirectResponse(
            f"/plan/{plan_id}/review?msg=Review+not+found&msg_type=error", status_code=303
        )

    return request.app.state.templates.TemplateResponse(
        "plan_review/report.html",
        {
            "request": request,
            "plan": plan,
            "review": review,
            "report": review.report or {},
        },
    )
