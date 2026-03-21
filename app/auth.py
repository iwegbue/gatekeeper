import logging

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse

from itsdangerous import URLSafeTimedSerializer

from app.config import settings
from app.database import get_db

logger = logging.getLogger(__name__)

serializer = URLSafeTimedSerializer(settings.SECRET_KEY)
SESSION_COOKIE = "gatekeeper_session"
MAX_SESSION_AGE = 86400 * 7  # 7 days


def create_session_token() -> str:
    return serializer.dumps({"authenticated": True})


def verify_session_token(token: str) -> bool:
    from itsdangerous.exc import BadSignature, SignatureExpired
    try:
        data = serializer.loads(token, max_age=MAX_SESSION_AGE)
        return data.get("authenticated", False)
    except (BadSignature, SignatureExpired):
        return False
    except Exception:
        logger.warning("Unexpected error during session token verification", exc_info=True)
        return False


class AuthMiddleware(BaseHTTPMiddleware):
    EXEMPT_PATHS = {"/login", "/static", "/api/", "/version"}

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        for exempt in self.EXEMPT_PATHS:
            if path.startswith(exempt):
                return await call_next(request)

        token = request.cookies.get(SESSION_COOKIE)
        if token and verify_session_token(token):
            return await call_next(request)

        return RedirectResponse(url="/login", status_code=302)


# ── Bearer token auth for API routes ──────────────────────────────────────────

_bearer_scheme = HTTPBearer(auto_error=False)


async def verify_api_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> None:
    """FastAPI dependency: validates Bearer token against stored hash."""
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing authorization header")

    from app.services.settings_service import verify_api_token_hash

    valid = await verify_api_token_hash(db, credentials.credentials)
    if not valid:
        raise HTTPException(status_code=401, detail="Invalid API token")
