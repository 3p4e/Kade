from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.api.deps import DbSession, require_role
from app.models.audit import AuditLog

router = APIRouter(prefix="/audit", tags=["audit"], dependencies=[Depends(require_role("admin"))])


@router.get("")
async def list_audit(
    session: DbSession,
    entity: str | None = None,
    entity_id: str | None = None,
    limit: int = Query(default=200, le=1000),
    offset: int = Query(default=0, ge=0),
):
    stmt = select(AuditLog).order_by(AuditLog.occurred_at.desc()).limit(limit).offset(offset)
    if entity:
        stmt = stmt.where(AuditLog.entity == entity)
    if entity_id:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    rows = (await session.execute(stmt)).scalars().all()
    return [
        {
            "id": r.id,
            "occurred_at": r.occurred_at.isoformat() if r.occurred_at else None,
            "actor_email": r.actor_email,
            "action": r.action,
            "entity": r.entity,
            "entity_id": r.entity_id,
            "before": r.before,
            "after": r.after,
        }
        for r in rows
    ]
