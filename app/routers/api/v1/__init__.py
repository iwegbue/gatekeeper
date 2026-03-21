from fastapi import APIRouter, Depends

from app.auth import verify_api_token
from app.routers.api.v1 import ai, ideas, instruments, journal, plan, reports, status, trades

# Auth router — no token dependency (it creates tokens)
from app.routers.api.v1 import auth as auth_router_module

# Protected router — all sub-routers require bearer token
api_v1_router = APIRouter(prefix="/api/v1", dependencies=[Depends(verify_api_token)])
api_v1_router.include_router(status.router)
api_v1_router.include_router(ideas.router)
api_v1_router.include_router(trades.router)
api_v1_router.include_router(journal.router)
api_v1_router.include_router(plan.router)
api_v1_router.include_router(instruments.router)
api_v1_router.include_router(reports.router)
api_v1_router.include_router(ai.router)

# Auth router — mounted separately without token dependency
api_v1_auth_router = APIRouter(prefix="/api/v1")
api_v1_auth_router.include_router(auth_router_module.router)
