from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services import idea_service, report_service, trade_service

router = APIRouter()


@router.get("/")
async def dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    active_ideas = await idea_service.list_ideas(db, active_only=True)
    open_trades = await trade_service.list_trades(db, open_only=True)
    trade_stats = await report_service.get_trade_stats(db)
    discipline_score = await report_service.get_discipline_score(db)

    return request.app.state.templates.TemplateResponse(
        "dashboard/index.html",
        {
            "request": request,
            "active_ideas": active_ideas,
            "open_trades": open_trades,
            "trade_stats": trade_stats,
            "discipline_score": discipline_score,
        },
    )
