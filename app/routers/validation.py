"""
Plan Validation Engine — HTML router.
"""

import asyncio
import logging
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.csrf import require_csrf
from app.database import get_db
from app.services import plan_service
from app.services.ai.factory import AIConfigError, get_provider_from_db
from app.services.validation import plan_compiler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/validation")


@router.get("")
async def validation_index(request: Request, db: AsyncSession = Depends(get_db)):
    active_plan = await plan_service.get_active_plan(db)
    runs = await plan_compiler.list_validation_runs(db, plan_id=active_plan.id if active_plan else None)
    return request.app.state.templates.TemplateResponse(
        "validation/history.html",
        {
            "request": request,
            "runs": runs,
            "active_plan": active_plan,
        },
    )


@router.post("/compile")
async def validation_compile(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _csrf: None = Depends(require_csrf),
):
    try:
        provider = await get_provider_from_db(db)
    except AIConfigError:
        return RedirectResponse(
            "/validation?msg=AI+provider+not+configured.+Configure+it+in+Settings.&msg_type=error",
            status_code=303,
        )

    try:
        run = await plan_compiler.start_compile(db)
        await db.commit()
    except Exception as exc:
        logger.exception("Failed to create validation run: %s", exc)
        return RedirectResponse(
            "/validation?msg=Could+not+start+validation.+Try+again.&msg_type=error",
            status_code=303,
        )

    # Fire-and-forget: compile runs in background, page polls for completion
    asyncio.create_task(plan_compiler.run_compile_in_background(run.id, provider))

    return RedirectResponse(f"/validation/runs/{run.id}", status_code=303)


@router.get("/runs/{run_id}/status")
async def validation_run_status(run_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """JSON endpoint for polling run completion."""
    from datetime import datetime, timezone

    from fastapi.responses import JSONResponse

    run = await plan_compiler.get_validation_run(db, run_id)
    if run is None:
        return JSONResponse({"status": "NOT_FOUND"}, status_code=404)

    # If the run has been stuck in COMPILING for >5 min, the background task
    # likely died (e.g. container restart). Mark it failed so the UI unblocks.
    if run.status in ("PENDING", "COMPILING") and run.started_at:
        age = (datetime.now(timezone.utc) - run.started_at).total_seconds()
        if age > 300:
            run.status = "FAILED"
            run.error_message = "Check timed out — please try again."
            # db.commit() is called automatically by get_db on exit

    return JSONResponse({"status": run.status})


@router.post("/runs/{run_id}/delete")
async def validation_run_delete(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _csrf: None = Depends(require_csrf),
):
    deleted = await plan_compiler.delete_validation_run(db, run_id)
    if not deleted:
        return RedirectResponse("/validation?msg=Check+not+found&msg_type=error", status_code=303)
    return RedirectResponse("/validation?msg=Check+deleted", status_code=303)


@router.get("/runs/{run_id}")
async def validation_run_detail(run_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db)):
    run = await plan_compiler.get_validation_run(db, run_id)
    if run is None:
        return RedirectResponse("/validation?msg=Run+not+found&msg_type=error", status_code=303)

    compiled_plan = await plan_compiler.get_compiled_plan(db, run.compiled_plan_id)
    if compiled_plan is None:
        return RedirectResponse("/validation?msg=Compiled+plan+not+found&msg_type=error", status_code=303)

    return request.app.state.templates.TemplateResponse(
        "validation/report.html",
        {
            "request": request,
            "run": run,
            "compiled_plan": compiled_plan,
            "feedback": run.feedback or {},
        },
    )
