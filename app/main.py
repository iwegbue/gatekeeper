import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.auth import AuthMiddleware
from app.mcp import create_mcp_server
from app.routers import (
    auth,
    dashboard,
    help,
    ideas,
    instruments,
    journal,
    plan,
    plan_builder,
    reports,
    settings,
    setup,
    trades,
    validation,
)
from app.routers.api.v1 import api_v1_auth_router, api_v1_router

limiter = Limiter(key_func=get_remote_address)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent

_version_file = BASE_DIR.parent / "version.json"
if _version_file.exists():
    _version_info = json.loads(_version_file.read_text())
else:
    _version_info = {"version": "dev", "commit": "local"}


_mcp_server = create_mcp_server()
# path="/" because we mount the sub-app at /mcp — avoids a /mcp/mcp double-prefix
_mcp_app = _mcp_server.http_app(path="/")


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.config import settings as _settings
    _settings.check_security()  # logs a warning if SECRET_KEY is still ephemeral

    # Seed admin password from env var if provided and no hash exists in the DB yet
    from app.database import AsyncSessionFactory
    from app.services.settings_service import admin_password_is_set, get_settings, set_admin_password
    async with AsyncSessionFactory() as db:
        password_set = await admin_password_is_set(db)
        if not password_set and _settings.ADMIN_PASSWORD:
            await set_admin_password(db, _settings.ADMIN_PASSWORD)
            await db.commit()
            password_set = True
            logger.info("Admin password seeded from ADMIN_PASSWORD env var")
        app.state.needs_setup = not password_set
        s = await get_settings(db)
        app.state.setup_completed = s.setup_completed

    logger.info("Gatekeeper Core starting up")
    from app.tasks.background import start_background_tasks
    start_background_tasks(app)
    async with _mcp_app.lifespan(app):
        yield
    logger.info("Gatekeeper Core shutting down")


def create_app() -> FastAPI:
    app = FastAPI(title="Gatekeeper Core", docs_url=None, redoc_url=None, lifespan=lifespan)

    # Rate limiting
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    app.state.version_info = _version_info

    @app.get("/version")
    async def version():
        return JSONResponse(_version_info)

    # Templates
    template_env = Environment(
        loader=FileSystemLoader(str(BASE_DIR / "templates")),
        autoescape=True,
    )
    template_env.globals["app_version"] = _version_info.get("version", "dev")
    template_env.globals["app_commit"] = _version_info.get("commit", "local")[:7]
    app.state.templates = _TemplateAdapter(template_env)

    # Static files
    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

    # Security headers middleware
    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-XSS-Protection"] = "0"  # Modern browsers ignore; CSP is the control
        # Only send HSTS when actually on HTTPS
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    # Auth middleware
    app.add_middleware(AuthMiddleware)

    # Routers
    app.include_router(setup.router)
    app.include_router(auth.router)
    app.include_router(dashboard.router)
    app.include_router(plan.router)
    app.include_router(ideas.router)
    app.include_router(trades.router)
    app.include_router(plan_builder.router)
    app.include_router(journal.router)
    app.include_router(instruments.router)
    app.include_router(settings.router)
    app.include_router(reports.router)
    app.include_router(validation.router)
    app.include_router(help.router)

    # JSON API v1
    app.include_router(api_v1_auth_router)
    app.include_router(api_v1_router)

    # MCP server (StreamableHTTP at /mcp)
    app.mount("/mcp", _mcp_app)

    return app


class _TemplateAdapter:
    """Adapts Jinja2 Environment to work like Starlette's Jinja2Templates."""

    def __init__(self, env: Environment):
        self.env = env

    def TemplateResponse(self, name: str, context: dict, status_code: int = 200):
        from starlette.responses import HTMLResponse

        from app.csrf import generate_csrf_token

        # Inject a fresh CSRF token for every HTML response
        context.setdefault("csrf_token", generate_csrf_token())
        template = self.env.get_template(name)
        html = template.render(**context)
        return HTMLResponse(content=html, status_code=status_code)


app = create_app()
