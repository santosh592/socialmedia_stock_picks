from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from models.entities import MarketBar, OpportunitySignal, RedditPost, Summary, TickerMention, TickerRollup
from services.summary.llm import SummaryService

router = APIRouter(tags=["tickers"])


@router.get("/tickers/{ticker}")
async def get_ticker(
    ticker: str,
    window: str = Query("7d"),
    profile: str = Query("swing", pattern="^(day|swing)$"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    symbol = ticker.upper()
    rollup_result = await db.execute(
        select(TickerRollup).where(
            TickerRollup.ticker == symbol,
            TickerRollup.window == window,
            TickerRollup.profile == profile,
        )
        .order_by(TickerRollup.computed_at.desc())
        .limit(1)
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

    post_ids_result = await db.execute(
        select(TickerMention.source_id)
        .where(
            TickerMention.ticker == symbol,
            TickerMention.source_type == "post",
        )
        .limit(20)
    )
    post_ids = [row[0] for row in post_ids_result.all()]
    top_posts = []
    if post_ids:
        posts_result = await db.execute(
            select(RedditPost)
            .where(RedditPost.id.in_(post_ids))
            .order_by(RedditPost.score.desc())
            .limit(10)
        )
        top_posts = [
            {
                "id": p.id,
                "subreddit": p.subreddit,
                "title": p.title,
                "score": p.score,
                "permalink": p.permalink,
            }
            for p in posts_result.scalars().all()
        ]

    bars_result = await db.execute(
        select(MarketBar)
        .where(MarketBar.ticker == symbol)
        .order_by(MarketBar.date.desc())
        .limit(30)
    )
    market_bars = [
        {
            "date": b.date.isoformat(),
            "close": b.close,
            "volume": b.volume,
        }
        for b in reversed(bars_result.scalars().all())
    ]

    opps_result = await db.execute(
        select(OpportunitySignal)
        .where(
            OpportunitySignal.ticker == symbol,
            OpportunitySignal.window == window,
        )
        .order_by(OpportunitySignal.score.desc())
    )

    return {
        "ticker": symbol,
        "window": window,
        "profile": profile,
        "rollup": {
            "mention_count": rollup.mention_count,
            "weighted_mentions": rollup.weighted_mentions,
            "unique_authors": rollup.unique_authors,
            "velocity_pct": rollup.velocity_pct,
            "rank_score": rollup.rank_score,
            "intent_counts": rollup.intent_counts,
        },
        "mention_timeline": [],
        "market_bars": market_bars,
        "top_posts": top_posts,
        "summary": summary.payload if summary else None,
        "opportunities": [
            {
                "type": o.type,
                "hypothesis": o.hypothesis,
                "confidence": o.confidence,
                "score": o.score,
                "inputs": o.inputs,
            }
            for o in opps_result.scalars().all()
        ],
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
