from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas import DashboardResponse, LastIngestInfo, OpportunityCard, TickerRow
from core.config import get_settings
from core.database import get_db
from models.entities import IngestRun, OpportunitySignal, TickerRollup

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardResponse)
async def dashboard(
    window: str | None = Query(None),
    profile: str = Query("day", pattern="^(day|swing)$"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> DashboardResponse:
    settings = get_settings()
    profile_cfg = settings.ranking.profiles.get(profile)
    effective_window = window or (profile_cfg.default_window if profile_cfg else "24h")

    rollup_result = await db.execute(
        select(TickerRollup)
        .where(TickerRollup.window == effective_window, TickerRollup.profile == profile)
        .order_by(TickerRollup.rank_score.desc())
        .limit(limit)
    )
    rollups = rollup_result.scalars().all()
    window_end = rollups[0].window_end if rollups else None

    ingest_result = await db.execute(
        select(IngestRun).order_by(IngestRun.started_at.desc()).limit(1)
    )
    ingest = ingest_result.scalar_one_or_none()
    last_ingest = LastIngestInfo(
        id=ingest.id if ingest else None,
        finished_at=ingest.finished_at if ingest else None,
        status=ingest.status if ingest else None,
    )

    tickers = [
        TickerRow(
            rank=i + 1,
            ticker=r.ticker,
            mention_count=r.mention_count,
            weighted_mentions=r.weighted_mentions,
            unique_authors=r.unique_authors,
            velocity_pct=r.velocity_pct,
        )
        for i, r in enumerate(rollups)
    ]

    opp_result = await db.execute(
        select(OpportunitySignal)
        .where(
            OpportunitySignal.window == effective_window,
            OpportunitySignal.profile == profile,
        )
        .order_by(OpportunitySignal.score.desc())
        .limit(10)
    )
    opportunities = [
        OpportunityCard(
            type=o.type,
            ticker=o.ticker,
            hypothesis=o.hypothesis,
            confidence=o.confidence,
            score=o.score,
        )
        for o in opp_result.scalars().all()
    ]

    return DashboardResponse(
        window=effective_window,
        window_end=window_end,
        profile=profile,
        last_ingest=last_ingest,
        tickers=tickers,
        opportunities=opportunities,
    )
