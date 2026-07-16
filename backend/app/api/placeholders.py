from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import CurrentUserDep, DbSession, require_role
from app.models.placeholder import PlaceholderField
from app.schemas.placeholder import PlaceholderApproval, PlaceholderIn, PlaceholderOut

router = APIRouter(prefix="/placeholders", tags=["placeholders"])


@router.get("", response_model=list[PlaceholderOut])
async def list_placeholders(
    session: DbSession,
    user: CurrentUserDep,
    status_filter: str | None = Query(default=None, alias="status"),
):
    stmt = select(PlaceholderField).order_by(PlaceholderField.occurrence_count.desc())
    if status_filter:
        stmt = stmt.where(PlaceholderField.status == status_filter)
    rows = (await session.execute(stmt)).scalars().all()
    return [PlaceholderOut.model_validate(r) for r in rows]


@router.post(
    "",
    response_model=PlaceholderOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("admin", "analyst"))],
)
async def create_placeholder(
    payload: PlaceholderIn, session: DbSession, user: CurrentUserDep
):
    existing = await session.execute(
        select(PlaceholderField).where(PlaceholderField.key.ilike(payload.key))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status.HTTP_409_CONFLICT, "Placeholder with that key already exists")
    ph = PlaceholderField(**payload.model_dump(), status="approved", approved_by=UUID(user.id),
                          approved_at=datetime.now(timezone.utc))
    session.add(ph)
    await session.commit()
    await session.refresh(ph)
    return PlaceholderOut.model_validate(ph)


@router.post(
    "/{ph_id}/decision",
    response_model=PlaceholderOut,
    dependencies=[Depends(require_role("admin"))],
)
async def decide_placeholder(
    ph_id: UUID, payload: PlaceholderApproval, session: DbSession, user: CurrentUserDep
):
    if payload.status not in {"approved", "deprecated"}:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "status must be approved or deprecated")
    ph = (
        await session.execute(select(PlaceholderField).where(PlaceholderField.id == ph_id))
    ).scalar_one_or_none()
    if not ph:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Placeholder not found")
    ph.status = payload.status
    ph.approved_at = datetime.now(timezone.utc)
    ph.approved_by = UUID(user.id)
    await session.commit()
    await session.refresh(ph)
    return PlaceholderOut.model_validate(ph)
