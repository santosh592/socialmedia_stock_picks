from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from models.entities import Summary, TickerRollup
from services.summary.llm import SummaryService

router = APIRouter(tags=["tickers"])


@router.get("/tickers/{ticker}")
async def get_ticker(
    ticker: str,
    window: str = Query("7d"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    symbol = ticker.upper()
    rollup_result = await db.execute(
        select(TickerRollup).where(
            TickerRollup.ticker == symbol,
            TickerRollup.window == window,
        )
    )
    rollup = rollup_result.scalar_one_or_none()
    if rollup is None:
        raise HTTPException(status_code=404, detail=f"No rollup for {symbol} in window {window}")

    summary_result = await db.execute(
        select(Summary)
        .where(Summary.ticker == symbol, Summary.window == window)
        .order_by(Summary.created_at.desc())
        .limit(1)
    )
    summary = summary_result.scalar_one_or_none()

    return {
        "ticker": symbol,
        "window": window,
        "rollup": {
            "mention_count": rollup.mention_count,
            "weighted_mentions": rollup.weighted_mentions,
            "unique_authors": rollup.unique_authors,
            "velocity_pct": rollup.velocity_pct,
            "rank_score": rollup.rank_score,
        },
        "mention_timeline": [],
        "market_bars": [],
        "top_posts": [],
        "summary": summary.payload if summary else None,
        "opportunities": [],
    }


@router.post("/tickers/{ticker}/summarize", status_code=200)
async def summarize_ticker(
    ticker: str,
    window: str = Query(...),
    force: bool = Query(False),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = SummaryService(db)
    payload = await service.generate(ticker.upper(), window, force=force)
    return {"summary": payload}

