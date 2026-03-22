"""
Plan Validation Engine — JSON API router (Phase 1: Interpretability).
"""

import uuid
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.validation import (
    CompiledPlanResponse,
    ConfirmCompiledRuleRequest,
    ValidationRunDetailResponse,
    ValidationRunResponse,
)
from app.services.ai.factory import AIConfigError, get_provider_from_db
from app.services.validation import feedback_service, plan_compiler

if TYPE_CHECKING:
    from app.services.ai.base import AIProvider

router = APIRouter(prefix="/validation", tags=["validation"])


async def get_validation_ai_provider(db: AsyncSession = Depends(get_db)) -> "AIProvider":
    """
    FastAPI dependency that resolves and returns the active AI provider.
    Raises HTTP 422 if no provider is configured.
    Exposed as a named dependency so tests can override it.
    """
    try:
        return await get_provider_from_db(db)
    except AIConfigError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/compile", response_model=ValidationRunDetailResponse, status_code=201)
async def compile_plan(
    db: AsyncSession = Depends(get_db),
    provider: "AIProvider" = Depends(get_validation_ai_provider),
):
    """
    Compile the current trading plan.
    Each rule is interpreted by the AI provider against the proxy vocabulary.
    Returns a ValidationRun with interpretability report and compiled rule details.
    """
    compiled_plan, run = await plan_compiler.compile_plan(db, provider)
    report = feedback_service.build_report(compiled_plan)
    run.feedback = report
    await db.flush()

    return _build_run_detail(run, compiled_plan)


@router.get("/runs", response_model=list[ValidationRunResponse])
async def list_runs(db: AsyncSession = Depends(get_db)):
    """List all past validation runs, newest first."""
    runs = await plan_compiler.list_validation_runs(db)
    return [ValidationRunResponse.model_validate(r) for r in runs]


@router.get("/runs/{run_id}", response_model=ValidationRunDetailResponse)
async def get_run(run_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get a single validation run with its compiled plan details."""
    run = await plan_compiler.get_validation_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Validation run not found")

    compiled_plan = await plan_compiler.get_compiled_plan(db, run.compiled_plan_id)
    if compiled_plan is None:
        raise HTTPException(status_code=404, detail="Compiled plan not found")

    return _build_run_detail(run, compiled_plan)


@router.put("/compiled-plans/{compiled_plan_id}/rules/{rule_id}/confirm", response_model=CompiledPlanResponse)
async def confirm_rule(
    compiled_plan_id: uuid.UUID,
    rule_id: str,
    body: ConfirmCompiledRuleRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    User confirms or overrides an AI-proposed rule interpretation.
    After confirmation the interpretability score and coherence warnings are recomputed.
    """
    updated = await plan_compiler.confirm_compiled_rule(
        db,
        compiled_plan_id,
        rule_id,
        status=body.status,
        proxy_type=body.proxy_type,
        proxy_params=body.proxy_params,
        interpretation_notes=body.interpretation_notes,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Compiled plan not found")

    return CompiledPlanResponse.model_validate(updated)


# ── Private helpers ───────────────────────────────────────────────────────────


def _build_run_detail(run, compiled_plan) -> ValidationRunDetailResponse:
    plan_data = CompiledPlanResponse.model_validate(compiled_plan)
    run_data = ValidationRunResponse.model_validate(run)
    return ValidationRunDetailResponse(
        **run_data.model_dump(),
        compiled_plan=plan_data,
    )
