"""FastAPI entrypoint."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.api import audit, auth, coas, dashboard, drive, labs, placeholders, rag
from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.ingestion.email_poller import poll_loop
from app.models.user import User
from app.services.ingestion_service import ingest_pdf

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("coa")


async def _ensure_bootstrap_admin() -> None:
    settings = get_settings()
    async with SessionLocal() as s:
        any_user = (await s.execute(select(User).limit(1))).scalar_one_or_none()
        if any_user:
            return
        s.add(
            User(
                email=settings.bootstrap_admin_email,
                password_hash=hash_password(settings.bootstrap_admin_password),
                full_name="Bootstrap Admin",
                role="admin",
            )
        )
        await s.commit()
        logger.info("Created bootstrap admin %s", settings.bootstrap_admin_email)


async def _on_email_pdf(path, sha, sender):
    """Callback used by the IMAP poller for each new PDF."""
    async with SessionLocal() as s:
        try:
            coa, _, _ = await ingest_pdf(
                s,
                path,
                original_filename=path.name,
                ingestion_method="email",
                actor_id=None,
            )
            await s.commit()
            logger.info("Email-ingested CoA %s from %s", coa.id, sender)
        except Exception:
            await s.rollback()
            logger.exception("Failed to ingest email PDF %s", path)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _ensure_bootstrap_admin()
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)

    poll_task: asyncio.Task | None = None
    if settings.imap_host and settings.imap_user:
        logger.info("Starting IMAP poller against %s", settings.imap_host)
        poll_task = asyncio.create_task(poll_loop(_on_email_pdf))

    try:
        yield
    finally:
        if poll_task:
            poll_task.cancel()
            try:
                await poll_task
            except (asyncio.CancelledError, Exception):
                pass


app = FastAPI(
    title="CoA Tracker",
    description="Certificate of Analysis ingestion, tracking, RAG and placeholder discovery.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(coas.router)
app.include_router(labs.router)
app.include_router(placeholders.router)
app.include_router(rag.router)
app.include_router(dashboard.router)
app.include_router(audit.router)
app.include_router(drive.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
