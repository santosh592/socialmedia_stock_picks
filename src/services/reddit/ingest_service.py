from __future__ import annotations

import logging

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import Settings, get_settings
from models.entities import PostIntent, RedditComment, RedditPost, TickerMention
from services.reddit.client import RedditClient
from services.reddit.types import IngestStats, RedditCommentData, RedditPostData
from services.ticker.extract import TickerExtractor
from services.ticker.intent import IntentClassifier

logger = logging.getLogger(__name__)


class RedditIngestService:
    def __init__(
        self,
        db: AsyncSession,
        *,
        settings: Settings | None = None,
        client: RedditClient | None = None,
    ) -> None:
        self.db = db
        self.settings = settings or get_settings()
        self.client = client or RedditClient(self.settings)
        self.extractor = TickerExtractor(self.settings)
        self.intent_classifier = IntentClassifier()

    async def ingest_all(self) -> IngestStats:
        stats = IngestStats()
        async with self.client:
            for subreddit in self.settings.reddit.subreddits:
                try:
                    sub_stats = await self._ingest_subreddit(subreddit)
                    stats.posts_fetched += sub_stats.posts_fetched
                    stats.comments_fetched += sub_stats.comments_fetched
                    stats.mentions_created += sub_stats.mentions_created
                except Exception as exc:
                    msg = f"{subreddit}: {exc}"
                    logger.exception(msg)
                    stats.errors.append(msg)
        return stats

    async def _ingest_subreddit(self, subreddit: str) -> IngestStats:
        stats = IngestStats()
        limit = self.settings.reddit.max_posts_per_sub_per_poll
        comment_cfg = self.settings.reddit.comment_fetch
        fetch_comments = comment_cfg.get("enabled", True)
        min_score = int(comment_cfg.get("min_post_score", 5))
        max_comments = int(comment_cfg.get("max_comments_per_post", 200))

        for sort in self.settings.reddit.poll_sorts:
            async for post in self.client.iter_posts(subreddit, sort, limit):
                await self._upsert_post(post)
                stats.posts_fetched += 1
                mentions = await self._process_post_mentions(post)
                stats.mentions_created += mentions

                if fetch_comments and post.score >= min_score:
                    comments = await self.client.fetch_comments(
                        post.id,
                        max_comments=max_comments,
                        min_score=0,
                    )
                    for comment in comments:
                        await self._upsert_comment(comment)
                        stats.comments_fetched += 1
                        stats.mentions_created += await self._process_comment_mentions(
                            comment, post.subreddit
                        )
        return stats

    async def _upsert_post(self, post: RedditPostData) -> bool:
        stmt = (
            insert(RedditPost)
            .values(
                id=post.id,
                subreddit=post.subreddit,
                author=post.author,
                created_utc=post.created_utc,
                title=post.title,
                body=post.body,
                url=post.url,
                score=post.score,
                num_comments=post.num_comments,
                flair=post.flair,
                permalink=post.permalink,
            )
            .on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "score": post.score,
                    "num_comments": post.num_comments,
                    "body": post.body,
                    "flair": post.flair,
                },
            )
        )
        result = await self.db.execute(stmt)
        return result.rowcount > 0

    async def _upsert_comment(self, comment: RedditCommentData) -> bool:
        stmt = (
            insert(RedditComment)
            .values(
                id=comment.id,
                post_id=comment.post_id,
                parent_id=comment.parent_id,
                author=comment.author,
                created_utc=comment.created_utc,
                body=comment.body,
                score=comment.score,
                permalink=comment.permalink,
            )
            .on_conflict_do_update(
                index_elements=["id"],
                set_={"score": comment.score, "body": comment.body},
            )
        )
        result = await self.db.execute(stmt)
        return result.rowcount > 0

    async def _process_post_mentions(self, post: RedditPostData) -> int:
        dd_flair = (post.flair or "").lower() == "dd"
        negative = post.score < 0
        text_parts = [("title", post.title), ("body", post.body or "")]
        intent, confidence = self.intent_classifier.classify(
            f"{post.title}\n{post.body or ''}"
        )
        await self.db.execute(
            insert(PostIntent)
            .values(post_id=post.id, intent=intent, confidence=confidence)
            .on_conflict_do_update(
                index_elements=["post_id"],
                set_={"intent": intent, "confidence": confidence},
            )
        )
        return await self._save_mentions(
            text_parts,
            source_type="post",
            source_id=post.id,
            subreddit=post.subreddit,
            created_utc=post.created_utc,
            dd_flair=dd_flair,
            negative_score=negative,
        )

    async def _process_comment_mentions(self, comment: RedditCommentData, subreddit: str) -> int:
        return await self._save_mentions(
            [("body", comment.body)],
            source_type="comment",
            source_id=comment.id,
            subreddit=subreddit,
            created_utc=comment.created_utc,
            dd_flair=False,
            negative_score=comment.score < 0,
        )

    async def _save_mentions(
        self,
        text_parts: list[tuple[str, str]],
        *,
        source_type: str,
        source_id: str,
        subreddit: str,
        created_utc,
        dd_flair: bool,
        negative_score: bool,
    ) -> int:
        created = 0
        seen: set[str] = set()
        for location, text in text_parts:
            for ticker in self.extractor.extract(text):
                if ticker in seen:
                    continue
                seen.add(ticker)
                weight = self.extractor.weight_for(
                    location,
                    dd_flair=dd_flair,
                    negative_score=negative_score,
                )
                stmt = (
                    insert(TickerMention)
                    .values(
                        ticker=ticker,
                        source_type=source_type,
                        source_id=source_id,
                        subreddit=subreddit,
                        weight=weight,
                        location=location,
                        created_utc=created_utc,
                    )
                    .on_conflict_do_nothing(constraint="uq_mention_source")
                )
                result = await self.db.execute(stmt)
                created += result.rowcount
        return created
