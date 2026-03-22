"""
Plan Validation Engine — HTML router.
"""
import logging
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.csrf import require_csrf
from app.database import get_db
from app.services.ai.factory import AIConfigError, get_provider_from_db
from app.services.validation import feedback_service, plan_compiler

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

    return request.app.state.templates.TemplateResponse(
        "validation/report.html",
        {
            "request": request,
            "run": run,
            "compiled_plan": compiled_plan,
            "feedback": run.feedback or {},
        },
    )
