from fastapi import APIRouter, Request
from starlette.responses import RedirectResponse

router = APIRouter()


@router.get("/")
async def dashboard(request: Request):
    return request.app.state.templates.TemplateResponse(
        "dashboard/index.html",
        {"request": request},
    )
