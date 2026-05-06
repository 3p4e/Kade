"""Orchestrates: PDF -> text -> field extraction -> placeholder discovery
-> chunking -> embeddings -> DB insert."""
from __future__ import annotations

import hashlib
import logging
from datetime import date
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.ingestion.extractor import ExtractionResult, extract
from app.ingestion.pdf import extract_pages
from app.models.coa import Coa, CoaChunk, CoaParameter
from app.models.lab import Laboratory
from app.models.placeholder import PlaceholderField
from app.rag.chunker import chunk_pages
from app.rag.embedder import embed_many

logger = logging.getLogger(__name__)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for buf in iter(lambda: f.read(1 << 20), b""):
            h.update(buf)
    return h.hexdigest()


def store_uploaded_pdf(content: bytes, original_filename: str, *, source: str) -> tuple[Path, str]:
    settings = get_settings()
    digest = hashlib.sha256(content).hexdigest()
    today = date.today()
    dest_dir = settings.data_dir / source / f"{today.year:04d}/{today.month:02d}/{today.day:02d}"
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in original_filename)[:200] or "upload.pdf"
    dest = dest_dir / safe
    if dest.exists():
        # If a name collides but content differs, suffix with hash
        existing = sha256_file(dest)
        if existing != digest:
            dest = dest_dir / f"{digest[:12]}_{safe}"
            dest.write_bytes(content)
    else:
        dest.write_bytes(content)
    return dest, digest


async def load_known_placeholders(session: AsyncSession) -> dict[str, dict[str, Any]]:
    rows = (await session.execute(select(PlaceholderField))).scalars().all()
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        out[r.key.lower()] = {
            "id": r.id,
            "label": r.label,
            "data_type": r.data_type,
            "status": r.status,
            "occurrence_count": r.occurrence_count,
        }
    return out


async def find_duplicate(session: AsyncSession, sha: str, batch_number: str | None) -> UUID | None:
    res = await session.execute(
        select(Coa.id).where(Coa.file_sha256 == sha).limit(1)
    )
    row = res.scalar_one_or_none()
    if row:
        return row
    if batch_number:
        res = await session.execute(
            select(Coa.id)
            .where(Coa.batch_number.isnot(None))
            .where(Coa.batch_number.ilike(batch_number))
            .order_by(Coa.created_at.desc())
            .limit(1)
        )
        return res.scalar_one_or_none()
    return None


async def upsert_placeholder_observations(
    session: AsyncSession,
    candidates: list[dict[str, Any]],
) -> list[str]:
    """Increment occurrence_count for known keys; insert new candidates as `proposed`."""
    new_keys: list[str] = []
    for cand in candidates:
        key = cand["key"]
        existing = await session.execute(
            select(PlaceholderField).where(PlaceholderField.key.ilike(key))
        )
        ph = existing.scalar_one_or_none()
        if ph:
            await session.execute(
                update(PlaceholderField)
                .where(PlaceholderField.id == ph.id)
                .values(occurrence_count=PlaceholderField.occurrence_count + 1)
            )
        else:
            ph = PlaceholderField(
                key=key,
                label=cand.get("label") or key,
                data_type="string",
                description=f"Auto-discovered. Sample: {cand.get('sample_value','')[:120]}",
                occurrence_count=1,
                status="proposed",
            )
            session.add(ph)
            new_keys.append(key)
    return new_keys


async def resolve_laboratory(
    session: AsyncSession, lab_name: str | None
) -> UUID | None:
    if not lab_name:
        return None
    name = lab_name.strip()
    if not name:
        return None
    res = await session.execute(
        select(Laboratory).where(Laboratory.name.ilike(name))
    )
    lab = res.scalar_one_or_none()
    if lab:
        return lab.id
    lab = Laboratory(name=name)
    session.add(lab)
    await session.flush()
    return lab.id


async def index_coa_for_rag(session: AsyncSession, coa: Coa, pages: list[tuple[int, str]]) -> int:
    """Chunk page texts, embed them, store as coa_chunks. Returns chunk count."""
    chunks = chunk_pages(pages)
    if not chunks:
        return 0
    vectors = embed_many([c.content for c in chunks])
    rows = []
    for c, v in zip(chunks, vectors):
        rows.append(
            CoaChunk(
                coa_id=coa.id,
                chunk_index=c.index,
                content=c.content,
                page=c.page,
                embedding=v,
                token_count=max(1, len(c.content) // 4),
            )
        )
    session.add_all(rows)
    return len(rows)


async def ingest_pdf(
    session: AsyncSession,
    pdf_path: Path,
    *,
    original_filename: str,
    ingestion_method: str,
    actor_id: UUID | None = None,
) -> tuple[Coa, ExtractionResult, list[str]]:
    """Full pipeline. Returns (coa, extraction, newly_proposed_placeholder_keys)."""
    pages = extract_pages(pdf_path)
    page_pairs = [(p.page, p.text) for p in pages]
    full_text = "\n\n".join(t for _, t in page_pairs)

    known_ph = await load_known_placeholders(session)
    extraction = extract(full_text, known_placeholders=known_ph)

    sha = sha256_file(pdf_path)
    batch = extraction.fields.get("batch_number")
    dup = await find_duplicate(session, sha, batch if isinstance(batch, str) else None)

    lab_id = await resolve_laboratory(session, extraction.fields.get("laboratory_name"))

    overall = None
    if extraction.parameters:
        statuses = {(p.get("pass_fail") or "").upper() for p in extraction.parameters}
        if "FAIL" in statuses:
            overall = "FAIL"
        elif "PASS" in statuses and "FAIL" not in statuses:
            overall = "PASS"
        else:
            overall = "REVIEW"

    coa = Coa(
        doc_code=extraction.fields.get("doc_code"),
        batch_number=extraction.fields.get("batch_number"),
        sample_id=extraction.fields.get("sample_id"),
        product_name=extraction.fields.get("product_name"),
        strain_name=extraction.fields.get("strain_name"),
        potency=extraction.fields.get("potency"),
        manufacturer_name=extraction.fields.get("manufacturer_name"),
        sample_receipt_date=extraction.fields.get("sample_receipt_date"),
        analysis_start_date=extraction.fields.get("analysis_start_date"),
        analysis_completion_date=extraction.fields.get("analysis_completion_date"),
        laboratory_id=lab_id,
        overall_status=overall,
        original_filename=original_filename,
        file_path=str(pdf_path),
        file_sha256=sha,
        ingestion_method=ingestion_method,
        extracted_text=full_text[:500_000],  # cap stored text
        extra_fields=extraction.extra_fields,
        created_by=actor_id,
        updated_by=actor_id,
    )
    if dup is not None:
        coa.extra_fields = {**coa.extra_fields, "_duplicate_of": str(dup)}

    session.add(coa)
    await session.flush()

    for p in extraction.parameters:
        session.add(CoaParameter(coa_id=coa.id, **p))

    new_keys = await upsert_placeholder_observations(session, extraction.candidate_placeholders)
    await index_coa_for_rag(session, coa, page_pairs)
    return coa, extraction, new_keys
