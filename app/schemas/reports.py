from pydantic import BaseModel


class TradeStatsResponse(BaseModel):
    total: int
    wins: int
    losses: int
    breakeven: int
    win_rate: float
    avg_r: float
    best_r: float | None = None
    worst_r: float | None = None
    expectancy: float


class DisciplineReportResponse(BaseModel):
    trade_stats: TradeStatsResponse
    grade_distribution: dict[str, int]
    adherence_stats: dict
    rule_violations: list[dict]
    discipline_score: float
    consistency_trend: list[dict]
    r_by_grade: dict[str, list[float]]
