from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    email: str


class CurrentUser(BaseModel):
    id: str
    email: str
    role: str
    full_name: str | None = None
