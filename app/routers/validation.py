"""
Plan Validation Engine — HTML router.
"""

import logging
import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.csrf import require_csrf
from app.database import get_db
from app.services.ai.factory import AIConfigError, get_provider_from_db
from app.services.validation import feedback_service, plan_compiler
from app.services.validation.replay_service import create_replay_run, run_replay_for_run

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/validation")


@router.get("")
async def validation_index(request: Request, db: AsyncSession = Depends(get_db)):
    runs = await plan_compiler.list_validation_runs(db)
    return request.app.state.templates.TemplateResponse(
        "validation/history.html",
        {
            "request": request,
            "runs": runs,
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
        compiled_plan, run = await plan_compiler.compile_plan(db, provider)
        report = feedback_service.build_report(compiled_plan)
        run.feedback = report
        await db.flush()
    except Exception as exc:
        logger.exception("Plan compilation failed: %s", exc)
        return RedirectResponse(
            "/validation?msg=Compilation+failed.+Check+your+AI+provider+settings.&msg_type=error",
            status_code=303,
        )

    return RedirectResponse(f"/validation/runs/{run.id}", status_code=303)


@router.get("/runs/{run_id}")
async def validation_run_detail(run_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db)):
    run = await plan_compiler.get_validation_run(db, run_id)
    if run is None:
        return RedirectResponse("/validation?msg=Run+not+found&msg_type=error", status_code=303)

    compiled_plan = await plan_compiler.get_compiled_plan(db, run.compiled_plan_id)
    if compiled_plan is None:
        return RedirectResponse("/validation?msg=Compiled+plan+not+found&msg_type=error", status_code=303)

    today = date.today()
    return request.app.state.templates.TemplateResponse(
        "validation/report.html",
        {
            "request": request,
            "run": run,
            "compiled_plan": compiled_plan,
            "feedback": run.feedback or {},
            "replay_default_start": (today - timedelta(days=365)).isoformat(),
            "replay_default_end": today.isoformat(),
        },
    )


@router.post("/runs/{run_id}/replay")
async def validation_run_replay_post(
    run_id: uuid.UUID,
    request: Request,
    symbol: str = Form(...),
    timeframe: str = Form("1d"),
    start_date: str = Form(...),
    end_date: str = Form(...),
    direction: str = Form("BOTH"),
    db: AsyncSession = Depends(get_db),
    _csrf: None = Depends(require_csrf),
):
    """Trigger a historical replay for a given interpretability run."""
    # Validate date inputs
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except ValueError:
        return RedirectResponse(
            f"/validation/runs/{run_id}?msg=Invalid+date+format.+Use+YYYY-MM-DD.&msg_type=error",
            status_code=303,
        )

    if end <= start:
        return RedirectResponse(
            f"/validation/runs/{run_id}?msg=End+date+must+be+after+start+date.&msg_type=error",
            status_code=303,
        )

    # Look up the interpretability run to get compiled_plan_id
    interp_run = await plan_compiler.get_validation_run(db, run_id)
    if interp_run is None:
        return RedirectResponse("/validation?msg=Run+not+found&msg_type=error", status_code=303)

    try:
        replay_run = await create_replay_run(
            db,
            compiled_plan_id=interp_run.compiled_plan_id,
            symbol=symbol,
            timeframe=timeframe,
            start_date=start,
            end_date=end,
            direction=direction,
        )
        await run_replay_for_run(db, replay_run.id)
    except Exception as exc:
        logger.exception("Replay failed for run %s: %s", run_id, exc)
        return RedirectResponse(
            f"/validation/runs/{run_id}?msg=Replay+failed%3A+{str(exc)[:80]}&msg_type=error",
            status_code=303,
        )

    return RedirectResponse(f"/validation/runs/{run_id}/replay", status_code=303)


@router.get("/runs/{run_id}/replay")
async def validation_run_replay_get(
    run_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Show the most recent completed replay for an interpretability run."""
    from app.models.validation.validation_run import ValidationRun

    interp_run = await plan_compiler.get_validation_run(db, run_id)
    if interp_run is None:
        return RedirectResponse("/validation?msg=Run+not+found&msg_type=error", status_code=303)

    # Find the most recent completed REPLAY run for the same compiled_plan_id
    result = await db.execute(
        select(ValidationRun)
        .where(
            ValidationRun.compiled_plan_id == interp_run.compiled_plan_id,
            ValidationRun.mode == "REPLAY",
            ValidationRun.status == "COMPLETED",
        )
        .order_by(ValidationRun.created_at.desc())
        .limit(1)
    )
    replay_run = result.scalar_one_or_none()

    if replay_run is None:
        return RedirectResponse(
            f"/validation/runs/{run_id}?msg=No+completed+replay+run+yet.&msg_type=info",
            status_code=303,
        )

    # Build R-distribution buckets for the chart
    trades = []
    if replay_run.summary_metrics:
        # We need the actual trade list — it's not in summary_metrics.
        # Re-run the engine isn't feasible here; we'll pass what we have.
        # Trade list is not persisted — only summary_metrics is.
        # The template will render KPI cards from summary_metrics.
        pass

    # Default replay form values for "Run Again"
    today = date.today()
    default_start = (today - timedelta(days=365)).isoformat()
    default_end = today.isoformat()
    settings = replay_run.settings or {}

    return request.app.state.templates.TemplateResponse(
        "validation/replay_report.html",
        {
            "request": request,
            "interp_run": interp_run,
            "replay_run": replay_run,
            "metrics": replay_run.summary_metrics or {},
            "settings": settings,
            "default_start": settings.get("start_date", default_start),
            "default_end": settings.get("end_date", default_end),
        },
    )
