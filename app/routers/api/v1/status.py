from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services import idea_service, trade_service

router = APIRouter(tags=["status"])


@router.get("/status")
async def status(request: Request, db: AsyncSession = Depends(get_db)):
    version_info = getattr(request.app.state, "version_info", {})
    active_ideas = await idea_service.list_ideas(db, active_only=True)
    open_trades = await trade_service.list_trades(db, open_only=True)
    return {
        "version": version_info.get("version", "dev"),
        "commit": version_info.get("commit", "local"),
        "active_ideas": len(active_ideas),
        "open_trades": len(open_trades),
    }
