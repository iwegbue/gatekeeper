import json

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services import report_service

router = APIRouter(prefix="/reports")


@router.get("")
async def reports_index(request: Request, db: AsyncSession = Depends(get_db)):
    trade_stats = await report_service.get_trade_stats(db)
    grade_dist = await report_service.get_grade_distribution(db)
    adherence_stats = await report_service.get_plan_adherence_stats(db)
    violations = await report_service.get_rule_violation_frequency(db)
    discipline_score = await report_service.get_discipline_score(db)
    trend_data = await report_service.get_consistency_trend(db, days=30)
    r_by_grade = await report_service.get_r_multiple_by_grade(db)

    return request.app.state.templates.TemplateResponse(
        "reports/index.html",
        {
            "request": request,
            "trade_stats": trade_stats,
            "grade_dist": grade_dist,
            "adherence_stats": adherence_stats,
            "violations": violations,
            "discipline_score": discipline_score,
            "trend_data_json": json.dumps(trend_data),
            "grade_dist_json": json.dumps(grade_dist),
            "r_by_grade_json": json.dumps(r_by_grade),
        },
    )
