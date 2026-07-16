from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUserDep, DbSession
from app.core.security import create_access_token, verify_password
from app.models.user import User
from app.schemas.auth import CurrentUser, LoginRequest, TokenResponse
from app.services.audit import log as audit_log

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, session: DbSession) -> TokenResponse:
    res = await session.execute(
        select(User).where(User.email.ilike(str(payload.email)))
    )
    user = res.scalar_one_or_none()
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    token = create_access_token(str(user.id), {"role": user.role, "email": user.email})
    await audit_log(
        session,
        actor_id=user.id,
        actor_email=user.email,
        action="login",
        entity="users",
        entity_id=str(user.id),
    )
    await session.commit()
    return TokenResponse(access_token=token, role=user.role, email=user.email)


@router.get("/me", response_model=CurrentUser)
async def me(user: CurrentUserDep) -> CurrentUser:
    return user
