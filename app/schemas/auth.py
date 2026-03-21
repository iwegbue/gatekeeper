from pydantic import BaseModel


class TokenGenerateRequest(BaseModel):
    password: str


class TokenGenerateResponse(BaseModel):
    token: str
