"""Background IMAP poller that pulls CoA PDFs from configured mailboxes."""
from __future__ import annotations

import asyncio
import email
import hashlib
import imaplib
import logging
import re
from datetime import datetime
from email.message import Message
from pathlib import Path

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _safe_filename(name: str) -> str:
    name = re.sub(r"[^\w.\-]+", "_", name)
    return name[:200] or "attachment.pdf"


def _save_pdf(part: Message, dest_dir: Path) -> tuple[Path, str] | None:
    payload = part.get_payload(decode=True)
    if not payload:
        return None
    digest = hashlib.sha256(payload).hexdigest()
    today = datetime.utcnow()
    dest = dest_dir / "email" / f"{today:%Y/%m/%d}"
    dest.mkdir(parents=True, exist_ok=True)
    fname = _safe_filename(part.get_filename() or f"{digest[:12]}.pdf")
    out = dest / fname
    if not out.exists():
        out.write_bytes(payload)
    return out, digest


def _poll_once() -> list[tuple[Path, str, str]]:
    """Connect, fetch unseen messages, save PDF attachments. Returns list of
    (path, sha256, sender)."""
    settings = get_settings()
    if not settings.imap_host or not settings.imap_user:
        return []

    saved: list[tuple[Path, str, str]] = []
    M = imaplib.IMAP4_SSL(settings.imap_host, settings.imap_port)
    try:
        M.login(settings.imap_user, settings.imap_password)
        M.select(settings.imap_folder)
        typ, data = M.search(None, "UNSEEN")
        if typ != "OK" or not data or not data[0]:
            return []
        for num in data[0].split():
            typ, msg_data = M.fetch(num, "(RFC822)")
            if typ != "OK" or not msg_data:
                continue
            msg = email.message_from_bytes(msg_data[0][1])
            sender = msg.get("From", "")
            for part in msg.walk():
                ctype = part.get_content_type()
                fname = part.get_filename() or ""
                if ctype == "application/pdf" or fname.lower().endswith(".pdf"):
                    res = _save_pdf(part, settings.data_dir)
                    if res:
                        saved.append((res[0], res[1], sender))
            M.store(num, "+FLAGS", "\\Seen")
    finally:
        try:
            M.close()
        except Exception:
            pass
        M.logout()
    return saved


async def poll_loop(on_pdf):
    """Long-running poller; calls `on_pdf(path, sha256, sender)` per file."""
    settings = get_settings()
    interval = max(30, settings.imap_poll_seconds)
    while True:
        try:
            results = await asyncio.to_thread(_poll_once)
            for path, sha, sender in results:
                try:
                    await on_pdf(path, sha, sender)
                except Exception:
                    logger.exception("on_pdf handler failed for %s", path)
        except Exception:
            logger.exception("IMAP poll failed")
        await asyncio.sleep(interval)
