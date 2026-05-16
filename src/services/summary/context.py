from __future__ import annotations

from datetime import datetime

from core.timeutil import UTC

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.entities import PostIntent, RedditComment, RedditPost, TickerMention, TickerRollup
from services.rollup.compute import parse_window


class SummaryContextBuilder:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def build(
        self,
        ticker: str,
        window: str,
        *,
        top_posts: int = 15,
        top_comments: int = 30,
    ) -> dict | None:
        window_end = datetime.now(UTC)
        window_start = window_end - parse_window(window)

        rollup_result = await self.db.execute(
            select(TickerRollup)
            .where(
                TickerRollup.ticker == ticker,
                TickerRollup.window == window,
            )
            .order_by(TickerRollup.computed_at.desc())
            .limit(1)
        )
        rollup = rollup_result.scalar_one_or_none()

        mentions_filter = (
            TickerMention.ticker == ticker,
            TickerMention.created_utc >= window_start,
            TickerMention.created_utc < window_end,
        )
        weighted_result = await self.db.execute(
            select(TickerMention.source_id, TickerMention.source_type).where(*mentions_filter)
        )
        sources = weighted_result.all()
        if not sources:
            return None

        post_ids = [sid for sid, st in sources if st == "post"]
        posts: list[RedditPost] = []
        if post_ids:
            post_result = await self.db.execute(
                select(RedditPost)
                .where(RedditPost.id.in_(post_ids))
                .order_by(RedditPost.score.desc())
                .limit(top_posts)
            )
            posts = list(post_result.scalars().all())

        comment_result = await self.db.execute(
            select(RedditComment)
            .join(
                TickerMention,
                (TickerMention.source_id == RedditComment.id)
                & (TickerMention.source_type == "comment"),
            )
            .where(*mentions_filter)
            .order_by(RedditComment.score.desc())
            .limit(top_comments)
        )
        comments = list(comment_result.scalars().all())

        intent_counts: dict[str, int] = {}
        if posts:
            intents = await self.db.execute(
                select(PostIntent).where(PostIntent.post_id.in_([p.id for p in posts]))
            )
            for intent_row in intents.scalars().all():
                intent_counts[intent_row.intent] = intent_counts.get(intent_row.intent, 0) + 1

        return {
            "ticker": ticker,
            "window": window,
            "window_end": window_end.isoformat(),
            "stats": {
                "weighted_mentions": rollup.weighted_mentions if rollup else 0,
                "unique_authors": rollup.unique_authors if rollup else 0,
                "velocity_pct": rollup.velocity_pct if rollup else 0,
                "intent_counts": intent_counts,
            },
            "posts": [
                {
                    "id": p.id,
                    "subreddit": p.subreddit,
                    "title": p.title[:500],
                    "body": (p.body or "")[:1500],
                    "score": p.score,
                    "permalink": p.permalink,
                }
                for p in posts
            ],
            "comments": [
                {
                    "id": c.id,
                    "post_id": c.post_id,
                    "body": c.body[:800],
                    "score": c.score,
                    "permalink": c.permalink,
                }
                for c in comments
            ],
            "source_ids": sorted({sid for sid, _ in sources}),
        }
