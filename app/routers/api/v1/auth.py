from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.auth import TokenGenerateRequest, TokenGenerateResponse
from app.services import settings_service

router = APIRouter(prefix="/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)


@router.post("/token", response_model=TokenGenerateResponse)
@limiter.limit("5/minute")
async def generate_token(
    request: Request,
    body: TokenGenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    if not await settings_service.verify_admin_password(db, body.password):
        raise HTTPException(status_code=401, detail="Invalid password")
    raw_token = await settings_service.generate_api_token(db)
    return TokenGenerateResponse(token=raw_token)
