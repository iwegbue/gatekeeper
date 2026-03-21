from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.reports import DisciplineReportResponse, TradeStatsResponse
from app.services import report_service

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/discipline", response_model=DisciplineReportResponse)
async def discipline_report(
    days: int = 30,
    db: AsyncSession = Depends(get_db),
):
    trade_stats = await report_service.get_trade_stats(db)
    grade_distribution = await report_service.get_grade_distribution(db)
    adherence_stats = await report_service.get_plan_adherence_stats(db)
    rule_violations = await report_service.get_rule_violation_frequency(db)
    discipline_score = await report_service.get_discipline_score(db)
    consistency_trend = await report_service.get_consistency_trend(db, days=days)
    r_by_grade = await report_service.get_r_multiple_by_grade(db)

    return DisciplineReportResponse(
        trade_stats=TradeStatsResponse(**trade_stats),
        grade_distribution=grade_distribution,
        adherence_stats=adherence_stats,
        rule_violations=rule_violations,
        discipline_score=discipline_score,
        consistency_trend=consistency_trend,
        r_by_grade=r_by_grade,
    )
