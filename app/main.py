import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader

from app.auth import AuthMiddleware
from app.routers import auth, dashboard, ideas, instruments, journal, plan, plan_builder, settings, trades

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Gatekeeper Core starting up")
    yield
    logger.info("Gatekeeper Core shutting down")


def create_app() -> FastAPI:
    app = FastAPI(title="Gatekeeper Core", docs_url=None, redoc_url=None, lifespan=lifespan)

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

    # Auth middleware
    app.add_middleware(AuthMiddleware)

    # Routers
    app.include_router(auth.router)
    app.include_router(dashboard.router)
    app.include_router(plan.router)
    app.include_router(ideas.router)
    app.include_router(trades.router)
    app.include_router(plan_builder.router)
    app.include_router(journal.router)
    app.include_router(instruments.router)
    app.include_router(settings.router)

    return app


class _TemplateAdapter:
    """Adapts Jinja2 Environment to work like Starlette's Jinja2Templates."""

    def __init__(self, env: Environment):
        self.env = env

    def TemplateResponse(self, name: str, context: dict, status_code: int = 200):
        from starlette.responses import HTMLResponse

        template = self.env.get_template(name)
        html = template.render(**context)
        return HTMLResponse(content=html, status_code=status_code)


app = create_app()
