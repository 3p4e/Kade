from datetime import date, timedelta

from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import CurrentUserDep, DbSession
from app.models.coa import Coa
from app.models.lab import Laboratory
from app.models.placeholder import PlaceholderField

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
async def summary(session: DbSession, user: CurrentUserDep):
    total = (await session.execute(select(func.count()).select_from(Coa))).scalar_one()
    pass_count = (
        await session.execute(select(func.count()).select_from(Coa).where(Coa.overall_status == "PASS"))
    ).scalar_one()
    fail_count = (
        await session.execute(select(func.count()).select_from(Coa).where(Coa.overall_status == "FAIL"))
    ).scalar_one()
    review_count = (
        await session.execute(select(func.count()).select_from(Coa).where(Coa.overall_status == "REVIEW"))
    ).scalar_one()

    cutoff = date.today() - timedelta(days=30)
    last_30 = (
        await session.execute(
            select(func.count()).select_from(Coa).where(Coa.ingested_at >= cutoff)
        )
    ).scalar_one()

    proposed_phs = (
        await session.execute(
            select(func.count()).select_from(PlaceholderField).where(PlaceholderField.status == "proposed")
        )
    ).scalar_one()

    expiring_labs = (
        await session.execute(
            select(Laboratory)
            .where(Laboratory.accreditation_valid_until.isnot(None))
            .where(Laboratory.accreditation_valid_until <= date.today() + timedelta(days=60))
            .order_by(Laboratory.accreditation_valid_until.asc())
            .limit(5)
        )
    ).scalars().all()

    recent = (
        await session.execute(
            select(Coa).order_by(Coa.ingested_at.desc()).limit(10)
        )
    ).scalars().all()

    return {
        "totals": {
            "all": total,
            "pass": pass_count,
            "fail": fail_count,
            "review": review_count,
            "last_30_days": last_30,
            "placeholders_proposed": proposed_phs,
        },
        "expiring_accreditations": [
            {
                "id": str(l.id),
                "name": l.name,
                "valid_until": l.accreditation_valid_until.isoformat()
                if l.accreditation_valid_until
                else None,
            }
            for l in expiring_labs
        ],
        "recent_coas": [
            {
                "id": str(c.id),
                "doc_code": c.doc_code,
                "batch_number": c.batch_number,
                "product_name": c.product_name,
                "overall_status": c.overall_status,
                "ingested_at": c.ingested_at.isoformat() if c.ingested_at else None,
            }
            for c in recent
        ],
    }
