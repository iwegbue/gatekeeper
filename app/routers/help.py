from fastapi import APIRouter, Request

router = APIRouter(prefix="/help")


@router.get("")
async def help_index(request: Request):
    return request.app.state.templates.TemplateResponse(
        "help/index.html",
        {"request": request},
    )
