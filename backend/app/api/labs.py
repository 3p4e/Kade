from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUserDep, DbSession, require_role
from app.models.lab import Laboratory, ServiceProvider
from app.schemas.lab import (
    LaboratoryIn,
    LaboratoryOut,
    ServiceProviderIn,
    ServiceProviderOut,
)

router = APIRouter(tags=["labs"])


@router.get("/laboratories", response_model=list[LaboratoryOut])
async def list_laboratories(session: DbSession, user: CurrentUserDep):
    rows = (await session.execute(select(Laboratory).order_by(Laboratory.name))).scalars().all()
    return [LaboratoryOut.model_validate(r) for r in rows]


@router.post(
    "/laboratories",
    response_model=LaboratoryOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("admin", "analyst"))],
)
async def create_lab(payload: LaboratoryIn, session: DbSession, user: CurrentUserDep):
    lab = Laboratory(**payload.model_dump())
    session.add(lab)
    await session.commit()
    await session.refresh(lab)
    return LaboratoryOut.model_validate(lab)


@router.patch(
    "/laboratories/{lab_id}",
    response_model=LaboratoryOut,
    dependencies=[Depends(require_role("admin", "analyst"))],
)
async def update_lab(
    lab_id: UUID, payload: LaboratoryIn, session: DbSession, user: CurrentUserDep
):
    lab = (
        await session.execute(select(Laboratory).where(Laboratory.id == lab_id))
    ).scalar_one_or_none()
    if not lab:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Laboratory not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(lab, k, v)
    await session.commit()
    await session.refresh(lab)
    return LaboratoryOut.model_validate(lab)


@router.get("/service-providers", response_model=list[ServiceProviderOut])
async def list_service_providers(session: DbSession, user: CurrentUserDep):
    rows = (
        await session.execute(select(ServiceProvider).order_by(ServiceProvider.name))
    ).scalars().all()
    return [ServiceProviderOut.model_validate(r) for r in rows]


@router.post(
    "/service-providers",
    response_model=ServiceProviderOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("admin", "analyst"))],
)
async def create_service_provider(
    payload: ServiceProviderIn, session: DbSession, user: CurrentUserDep
):
    sp = ServiceProvider(**payload.model_dump())
    session.add(sp)
    await session.commit()
    await session.refresh(sp)
    return ServiceProviderOut.model_validate(sp)
