"""Audit log helper."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


async def log(
    session: AsyncSession,
    *,
    actor_id: UUID | None,
    actor_email: str | None,
    action: str,
    entity: str,
    entity_id: str | None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    session.add(
        AuditLog(
            actor_id=actor_id,
            actor_email=actor_email,
            action=action,
            entity=entity,
            entity_id=entity_id,
            before=before,
            after=after,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    )
