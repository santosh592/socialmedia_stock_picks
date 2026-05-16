from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from datetime import datetime

from core.timeutil import UTC

import asyncpraw

from core.config import Settings, get_settings
from services.reddit.types import RedditCommentData, RedditPostData

logger = logging.getLogger(__name__)

SORT_METHODS = {
    "new": lambda sub: sub.new(),
    "hot": lambda sub: sub.hot(),
    "rising": lambda sub: sub.rising(),
    "top": lambda sub: sub.top(),
}


class RedditClient:
    """Async Reddit API wrapper using official OAuth (script app)."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._reddit: asyncpraw.Reddit | None = None

    def _credentials_ok(self) -> bool:
        r = self.settings.reddit
        return bool(r.client_id and r.client_secret and r.username and r.password)

    async def __aenter__(self) -> RedditClient:
        if not self._credentials_ok():
            raise ValueError(
                "Reddit credentials incomplete. Set REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, "
                "REDDIT_USERNAME, and REDDIT_PASSWORD in .env"
            )
        r = self.settings.reddit
        self._reddit = asyncpraw.Reddit(
            client_id=r.client_id,
            client_secret=r.client_secret,
            username=r.username,
            password=r.password,
            user_agent=r.user_agent,
        )
        return self

    async def __aexit__(self, *args: object) -> None:
        if self._reddit is not None:
            await self._reddit.close()
            self._reddit = None

    async def iter_posts(
        self,
        subreddit: str,
        sort: str,
        limit: int,
    ) -> AsyncIterator[RedditPostData]:
        if self._reddit is None:
            raise RuntimeError("RedditClient not opened; use async with")
        sort_fn = SORT_METHODS.get(sort)
        if sort_fn is None:
            raise ValueError(f"Unsupported sort: {sort}")
        sub = await self._reddit.subreddit(subreddit)
        count = 0
        async for submission in sort_fn(sub):
            if count >= limit:
                break
            count += 1
            yield self._map_submission(submission, subreddit)

    async def fetch_comments(
        self,
        post_id: str,
        *,
        max_comments: int,
        min_score: int = 0,
    ) -> list[RedditCommentData]:
        if self._reddit is None:
            raise RuntimeError("RedditClient not opened; use async with")
        submission = await self._reddit.submission(id=post_id.removeprefix("t3_"))
        submission.comment_sort = "top"
        await submission.comments.replace_more(limit=0)
        comments: list[RedditCommentData] = []
        for comment in submission.comments.list()[:max_comments]:
            if getattr(comment, "author", None) is None:
                continue
            if comment.score < min_score:
                continue
            comments.append(self._map_comment(comment, post_id))
        return comments

    @staticmethod
    def _map_submission(submission: asyncpraw.models.Submission, subreddit: str) -> RedditPostData:
        created = datetime.fromtimestamp(float(submission.created_utc), tz=UTC)
        permalink = f"https://reddit.com{submission.permalink}"
        return RedditPostData(
            id=f"t3_{submission.id}",
            subreddit=subreddit,
            author=str(submission.author) if submission.author else "[deleted]",
            created_utc=created,
            title=submission.title or "",
            body=submission.selftext or None,
            url=getattr(submission, "url", None),
            score=int(submission.score or 0),
            num_comments=int(submission.num_comments or 0),
            flair=getattr(submission, "link_flair_text", None),
            permalink=permalink,
        )

    @staticmethod
    def _map_comment(comment: asyncpraw.models.Comment, post_id: str) -> RedditCommentData:
        created = datetime.fromtimestamp(float(comment.created_utc), tz=UTC)
        permalink = f"https://reddit.com{comment.permalink}"
        parent = getattr(comment, "parent_id", None)
        return RedditCommentData(
            id=f"t1_{comment.id}",
            post_id=post_id,
            parent_id=parent,
            author=str(comment.author) if comment.author else "[deleted]",
            created_utc=created,
            body=comment.body or "",
            score=int(comment.score or 0),
            permalink=permalink,
        )
