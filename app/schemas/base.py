from pydantic import BaseModel


class ErrorResponse(BaseModel):
    detail: str
    code: str
    errors: list[str] = []


class SuccessResponse(BaseModel):
    ok: bool = True
    message: str = ""
