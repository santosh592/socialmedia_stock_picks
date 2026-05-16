from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import Settings, get_settings
from models.entities import RedditComment, RedditPost, TickerMention, TickerRollup

WINDOW_DELTAS = {
    "1h": timedelta(hours=1),
    "4h": timedelta(hours=4),
    "24h": timedelta(hours=24),
    "3d": timedelta(days=3),
    "7d": timedelta(days=7),
    "14d": timedelta(days=14),
    "30d": timedelta(days=30),
}


def parse_window(window: str) -> timedelta:
    if window not in WINDOW_DELTAS:
        raise ValueError(f"Unsupported window: {window}")
    return WINDOW_DELTAS[window]


class RollupService:
    """Computes ticker rollups for configured windows and profiles."""

    def __init__(self, db: AsyncSession, settings: Settings | None = None) -> None:
        self.db = db
        self.settings = settings or get_settings()

    async def recompute_all(self, window_end: datetime | None = None) -> int:
        end = window_end or datetime.now(UTC)
        count = 0
        for window in self.settings.aggregation.windows:
            for profile in self.settings.ranking.profiles:
                count += await self._recompute_window(window, end, profile)
        await self.db.commit()
        return count

    async def _recompute_window(self, window: str, window_end: datetime, profile: str) -> int:
        delta = parse_window(window)
        window_start = window_end - delta
        prev_end = window_start
        prev_start = prev_end - delta

        tickers_result = await self.db.execute(
            select(TickerMention.ticker)
            .where(
                TickerMention.created_utc >= window_start,
                TickerMention.created_utc < window_end,
            )
            .group_by(TickerMention.ticker)
        )
        tickers = [row[0] for row in tickers_result.all()]
        written = 0
        for ticker in tickers:
            metrics = await self._metrics_for_ticker(
                ticker, window_start, window_end, prev_start, prev_end
            )
            if metrics["mention_count"] < self.settings.aggregation.min_mentions_for_ticker_listing:
                continue
            rank_score = self._rank_score(metrics, profile)
            rollup = TickerRollup(
                ticker=ticker,
                window=window,
                window_end=window_end,
                mention_count=metrics["mention_count"],
                weighted_mentions=metrics["weighted_mentions"],
                unique_authors=metrics["unique_authors"],
                velocity_pct=metrics["velocity_pct"],
                engagement_depth=metrics["engagement_depth"],
                subreddit_breadth=metrics["subreddit_breadth"],
                intent_counts=metrics.get("intent_counts"),
                rank_score=rank_score,
                profile=profile,
            )
            await self.db.merge(rollup)
            written += 1
        return written

    async def _metrics_for_ticker(
        self,
        ticker: str,
        start: datetime,
        end: datetime,
        prev_start: datetime,
        prev_end: datetime,
    ) -> dict:
        base_filter = (
            TickerMention.ticker == ticker,
            TickerMention.created_utc >= start,
            TickerMention.created_utc < end,
        )
        agg = await self.db.execute(
            select(
                func.count(TickerMention.id),
                func.coalesce(func.sum(TickerMention.weight), 0.0),
                func.count(func.distinct(TickerMention.subreddit)),
            ).where(*base_filter)
        )
        mention_count, weighted, breadth = agg.one()

        prev_agg = await self.db.execute(
            select(func.coalesce(func.sum(TickerMention.weight), 0.0)).where(
                TickerMention.ticker == ticker,
                TickerMention.created_utc >= prev_start,
                TickerMention.created_utc < prev_end,
            )
        )
        prev_weighted = float(prev_agg.scalar_one() or 0.0)
        velocity = (
            ((float(weighted) - prev_weighted) / max(prev_weighted, 1.0)) * 100.0
            if prev_weighted or weighted
            else 0.0
        )

        authors: set[str] = set()
        post_authors = await self.db.execute(
            select(RedditPost.author)
            .join(
                TickerMention,
                (TickerMention.source_id == RedditPost.id)
                & (TickerMention.source_type == "post"),
            )
            .where(*base_filter)
        )
        authors.update(row[0] for row in post_authors.all())
        comment_authors = await self.db.execute(
            select(RedditComment.author)
            .join(
                TickerMention,
                (TickerMention.source_id == RedditComment.id)
                & (TickerMention.source_type == "comment"),
            )
            .where(*base_filter)
        )
        authors.update(row[0] for row in comment_authors.all())

        depth_result = await self.db.execute(
            select(func.avg(RedditPost.num_comments))
            .join(
                TickerMention,
                (TickerMention.source_id == RedditPost.id)
                & (TickerMention.source_type == "post"),
            )
            .where(*base_filter)
        )
        engagement_depth = float(depth_result.scalar_one() or 0.0)

        return {
            "mention_count": int(mention_count),
            "weighted_mentions": float(weighted),
            "unique_authors": len(authors),
            "velocity_pct": velocity,
            "engagement_depth": engagement_depth,
            "subreddit_breadth": int(breadth),
        }

    def _rank_score(self, metrics: dict, profile: str) -> float:
        cfg = self.settings.ranking.profiles.get(profile)
        if not cfg:
            return metrics["weighted_mentions"]
        w = cfg.weights
        score = (
            w.get("unique_authors", 0) * metrics["unique_authors"]
            + w.get("velocity", 0) * metrics["velocity_pct"]
            + w.get("weighted_mentions", 0) * metrics["weighted_mentions"]
            + w.get("engagement_depth", 0) * metrics["engagement_depth"]
            + w.get("subreddit_breadth", 0) * metrics["subreddit_breadth"]
        )
        return score
