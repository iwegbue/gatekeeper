"""
CSRF protection using itsdangerous signed tokens.

Usage:
  - In any POST route: call `verify_csrf(request)` before processing the form.
  - In templates: render `{{ csrf_token }}` inside every <form>.
  - The `csrf_token` global is injected into every TemplateResponse via the
    middleware that also sets `request.state.csrf_token`.

Token lifetime: 1 hour. Tokens are per-session (signed with SECRET_KEY).
"""

import logging
from typing import Annotated

from fastapi import Form, HTTPException, Request
from itsdangerous import URLSafeTimedSerializer
from itsdangerous.exc import BadSignature, SignatureExpired

from app.config import settings

logger = logging.getLogger(__name__)

_serializer = URLSafeTimedSerializer(settings.SECRET_KEY, salt="csrf")
_CSRF_MAX_AGE = 3600  # 1 hour
_CSRF_FIELD = "csrf_token"


def generate_csrf_token() -> str:
    return _serializer.dumps("csrf")


def verify_csrf_token(token: str) -> bool:
    try:
        _serializer.loads(token, max_age=_CSRF_MAX_AGE)
        return True
    except (BadSignature, SignatureExpired):
        return False
    except Exception:
        logger.warning("Unexpected error during CSRF token verification", exc_info=True)
        return False


async def require_csrf(
    request: Request,
    csrf_token: Annotated[str, Form(alias=_CSRF_FIELD)] = "",
) -> None:
    """FastAPI dependency: raises 403 if the CSRF token is missing or invalid."""
    if not verify_csrf_token(csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")
