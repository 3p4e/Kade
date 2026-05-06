from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUserDep, DbSession, require_role
from app.models.coa import Coa, CoaParameter
from app.schemas.coa import (
    CoaCreate,
    CoaListItem,
    CoaListResponse,
    CoaOut,
    CoaUpdate,
)
from app.services.audit import log as audit_log
from app.services.ingestion_service import ingest_pdf, store_uploaded_pdf

router = APIRouter(prefix="/coas", tags=["coas"])


@router.get("", response_model=CoaListResponse)
async def list_coas(
    session: DbSession,
    user: CurrentUserDep,
    q: str | None = Query(default=None, description="Full-text query"),
    laboratory_id: UUID | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
) -> CoaListResponse:
    stmt = select(Coa)
    count_stmt = select(func.count()).select_from(Coa)
    conds = []
    if q:
        # Combine FTS + ILIKE fallback for short queries
        ts = func.plainto_tsquery("english", q)
        conds.append(
            or_(
                Coa.search_tsv.op("@@")(ts) if hasattr(Coa, "search_tsv") else False,
                Coa.doc_code.ilike(f"%{q}%"),
                Coa.batch_number.ilike(f"%{q}%"),
                Coa.product_name.ilike(f"%{q}%"),
                Coa.strain_name.ilike(f"%{q}%"),
            )
        )
    if laboratory_id:
        conds.append(Coa.laboratory_id == laboratory_id)
    if status_filter:
        conds.append(Coa.overall_status == status_filter)
    if date_from:
        conds.append(Coa.analysis_completion_date >= date_from)
    if date_to:
        conds.append(Coa.analysis_completion_date <= date_to)
    if conds:
        for c in conds:
            stmt = stmt.where(c)
            count_stmt = count_stmt.where(c)
    stmt = stmt.order_by(Coa.ingested_at.desc()).limit(limit).offset(offset)
    rows = (await session.execute(stmt)).scalars().all()
    total = (await session.execute(count_stmt)).scalar_one()
    return CoaListResponse(
        items=[CoaListItem.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{coa_id}", response_model=CoaOut)
async def get_coa(coa_id: UUID, session: DbSession, user: CurrentUserDep) -> CoaOut:
    stmt = select(Coa).where(Coa.id == coa_id).options(selectinload(Coa.parameters))
    coa = (await session.execute(stmt)).scalar_one_or_none()
    if not coa:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "CoA not found")
    return CoaOut.model_validate(coa)


@router.post("", response_model=CoaOut, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_role("admin", "analyst"))])
async def create_coa(payload: CoaCreate, session: DbSession, user: CurrentUserDep) -> CoaOut:
    coa = Coa(
        **payload.model_dump(exclude={"parameters"}),
        created_by=UUID(user.id),
        updated_by=UUID(user.id),
    )
    session.add(coa)
    await session.flush()
    for p in payload.parameters or []:
        session.add(CoaParameter(coa_id=coa.id, **p.model_dump()))
    await audit_log(
        session,
        actor_id=UUID(user.id),
        actor_email=user.email,
        action="create",
        entity="coas",
        entity_id=str(coa.id),
        after=payload.model_dump(mode="json"),
    )
    await session.commit()
    await session.refresh(coa, attribute_names=["parameters"])
    return CoaOut.model_validate(coa)


@router.patch("/{coa_id}", response_model=CoaOut,
              dependencies=[Depends(require_role("admin", "analyst"))])
async def update_coa(
    coa_id: UUID,
    payload: CoaUpdate,
    session: DbSession,
    user: CurrentUserDep,
) -> CoaOut:
    stmt = select(Coa).where(Coa.id == coa_id).options(selectinload(Coa.parameters))
    coa = (await session.execute(stmt)).scalar_one_or_none()
    if not coa:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "CoA not found")

    before = {
        "doc_code": coa.doc_code,
        "batch_number": coa.batch_number,
        "overall_status": coa.overall_status,
        "extra_fields": coa.extra_fields,
    }
    data = payload.model_dump(exclude_unset=True, exclude={"parameters"})
    for k, v in data.items():
        setattr(coa, k, v)
    coa.updated_by = UUID(user.id)
    coa.version = (coa.version or 1) + 1

    if payload.parameters is not None:
        # Replace all parameters
        await session.execute(
            CoaParameter.__table__.delete().where(CoaParameter.coa_id == coa.id)
        )
        for p in payload.parameters:
            session.add(CoaParameter(coa_id=coa.id, **p.model_dump()))

    await audit_log(
        session,
        actor_id=UUID(user.id),
        actor_email=user.email,
        action="update",
        entity="coas",
        entity_id=str(coa.id),
        before=before,
        after=data,
    )
    await session.commit()
    await session.refresh(coa, attribute_names=["parameters"])
    return CoaOut.model_validate(coa)


@router.delete("/{coa_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(require_role("admin"))])
async def delete_coa(coa_id: UUID, session: DbSession, user: CurrentUserDep) -> None:
    coa = (await session.execute(select(Coa).where(Coa.id == coa_id))).scalar_one_or_none()
    if not coa:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "CoA not found")
    await audit_log(
        session,
        actor_id=UUID(user.id),
        actor_email=user.email,
        action="delete",
        entity="coas",
        entity_id=str(coa.id),
        before={"doc_code": coa.doc_code, "batch_number": coa.batch_number},
    )
    await session.delete(coa)
    await session.commit()


@router.get("/{coa_id}/file")
async def download_pdf(coa_id: UUID, session: DbSession, user: CurrentUserDep):
    coa = (await session.execute(select(Coa).where(Coa.id == coa_id))).scalar_one_or_none()
    if not coa or not coa.file_path:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "PDF not found")
    return FileResponse(
        coa.file_path,
        media_type="application/pdf",
        filename=coa.original_filename or f"{coa_id}.pdf",
    )


@router.post("/upload", response_model=CoaOut, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_role("admin", "analyst"))])
async def upload_pdf(
    session: DbSession,
    user: CurrentUserDep,
    file: Annotated[UploadFile, File(description="CoA PDF")],
    ingestion_method: Annotated[str, Form()] = "upload",
) -> CoaOut:
    if (file.content_type or "").lower() not in {"application/pdf", "application/octet-stream"}:
        # Some browsers send octet-stream; we'll still accept it but warn via filename
        if not (file.filename or "").lower().endswith(".pdf"):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only PDF files are accepted")
    if ingestion_method not in {"upload", "scan", "email", "api"}:
        ingestion_method = "upload"

    content = await file.read()
    if not content:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Empty file")

    path, _digest = store_uploaded_pdf(
        content,
        file.filename or "upload.pdf",
        source=ingestion_method,
    )

    coa, extraction, new_keys = await ingest_pdf(
        session,
        path,
        original_filename=file.filename or path.name,
        ingestion_method=ingestion_method,
        actor_id=UUID(user.id),
    )

    await audit_log(
        session,
        actor_id=UUID(user.id),
        actor_email=user.email,
        action="ingest",
        entity="coas",
        entity_id=str(coa.id),
        after={
            "ingestion_method": ingestion_method,
            "doc_code": coa.doc_code,
            "batch_number": coa.batch_number,
            "discovered_placeholders": new_keys,
        },
    )
    await session.commit()
    await session.refresh(coa, attribute_names=["parameters"])
    return CoaOut.model_validate(coa)
