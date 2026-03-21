from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse

from itsdangerous import URLSafeTimedSerializer

from app.config import settings

serializer = URLSafeTimedSerializer(settings.SECRET_KEY)
SESSION_COOKIE = "gatekeeper_session"
MAX_SESSION_AGE = 86400 * 7  # 7 days


def create_session_token() -> str:
    return serializer.dumps({"authenticated": True})


def verify_session_token(token: str) -> bool:
    try:
        data = serializer.loads(token, max_age=MAX_SESSION_AGE)
        return data.get("authenticated", False)
    except Exception:
        return False


class AuthMiddleware(BaseHTTPMiddleware):
    EXEMPT_PATHS = {"/login", "/static"}

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        for exempt in self.EXEMPT_PATHS:
            if path.startswith(exempt):
                return await call_next(request)

        token = request.cookies.get(SESSION_COOKIE)
        if token and verify_session_token(token):
            return await call_next(request)

        return RedirectResponse(url="/login", status_code=302)
