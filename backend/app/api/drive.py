"""Drive ingestion: pull PDFs from a public Google Drive URL into the system.

This endpoint expects a publicly-shared Drive folder/file URL. It does not
authenticate with Google; it uses Google's "uc?export=download" public endpoint.
For private folders, use the admin's own credentials and POST individual PDFs to
/coas/upload.
"""
from __future__ import annotations

import logging
import re
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.deps import CurrentUserDep, DbSession, require_role
from app.services.audit import log as audit_log
from app.services.ingestion_service import ingest_pdf, store_uploaded_pdf

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/drive", tags=["drive"], dependencies=[Depends(require_role("admin", "analyst"))])


class DriveFileIn(BaseModel):
    file_ids: list[str]
    ingestion_method: str = "upload"


class DriveFileResult(BaseModel):
    file_id: str
    coa_id: UUID | None = None
    doc_code: str | None = None
    batch_number: str | None = None
    error: str | None = None


@router.post("/ingest", response_model=list[DriveFileResult])
async def ingest_from_drive(
    payload: DriveFileIn, session: DbSession, user: CurrentUserDep
) -> list[DriveFileResult]:
    if not payload.file_ids:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "file_ids cannot be empty")

    results: list[DriveFileResult] = []
    async with httpx.AsyncClient(follow_redirects=True, timeout=60) as client:
        for fid in payload.file_ids:
            fid = fid.strip()
            if not re.fullmatch(r"[A-Za-z0-9_\-]{10,}", fid):
                results.append(DriveFileResult(file_id=fid, error="invalid file id"))
                continue
            try:
                # Public download URL. For private files this returns an HTML page,
                # not a PDF — handled via content-type check below.
                resp = await client.get(
                    "https://drive.google.com/uc",
                    params={"export": "download", "id": fid},
                )
                if resp.status_code != 200:
                    results.append(DriveFileResult(file_id=fid, error=f"http {resp.status_code}"))
                    continue
                ctype = resp.headers.get("content-type", "")
                if "pdf" not in ctype.lower() and not resp.content[:4] == b"%PDF":
                    results.append(
                        DriveFileResult(
                            file_id=fid,
                            error="not a public PDF (private file or virus scan interstitial)",
                        )
                    )
                    continue
                content = resp.content
                fname = f"drive_{fid}.pdf"
                disp = resp.headers.get("content-disposition", "")
                m = re.search(r'filename="?([^";]+)"?', disp)
                if m:
                    fname = m.group(1)

                path, _ = store_uploaded_pdf(
                    content, fname, source=payload.ingestion_method
                )
                coa, _, _ = await ingest_pdf(
                    session,
                    path,
                    original_filename=fname,
                    ingestion_method=payload.ingestion_method,
                    actor_id=UUID(user.id),
                )
                await audit_log(
                    session,
                    actor_id=UUID(user.id),
                    actor_email=user.email,
                    action="ingest",
                    entity="coas",
                    entity_id=str(coa.id),
                    after={"source": "drive", "drive_file_id": fid, "filename": fname},
                )
                await session.commit()
                results.append(
                    DriveFileResult(
                        file_id=fid,
                        coa_id=coa.id,
                        doc_code=coa.doc_code,
                        batch_number=coa.batch_number,
                    )
                )
            except Exception as e:
                logger.exception("drive ingest failed for %s", fid)
                await session.rollback()
                results.append(DriveFileResult(file_id=fid, error=str(e)[:200]))
    return results
