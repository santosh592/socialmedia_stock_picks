from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas import OpportunityCard
from core.config import get_settings
from core.database import get_db
from models.entities import OpportunitySignal

router = APIRouter(tags=["opportunities"])


@router.get("/opportunities", response_model=list[OpportunityCard])
async def list_opportunities(
    window: str | None = Query(None),
    profile: str = Query("day", pattern="^(day|swing)$"),
    type: str | None = Query(None, alias="type"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> list[OpportunityCard]:
    settings = get_settings()
    profile_cfg = settings.ranking.profiles.get(profile)
    effective_window = window or (profile_cfg.default_window if profile_cfg else "24h")

    query = (
        select(OpportunitySignal)
        .where(
            OpportunitySignal.window == effective_window,
            OpportunitySignal.profile == profile,
        )
        .order_by(OpportunitySignal.score.desc())
        .limit(limit)
    )
    if type:
        query = query.where(OpportunitySignal.type == type)

    result = await db.execute(query)
    return [
        OpportunityCard(
            type=o.type,
            ticker=o.ticker,
            hypothesis=o.hypothesis,
            confidence=o.confidence,
            score=o.score,
        )
        for o in result.scalars().all()
    ]
