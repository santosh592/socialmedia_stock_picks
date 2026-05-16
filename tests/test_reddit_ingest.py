from __future__ import annotations

import os
from collections.abc import AsyncIterator
from datetime import datetime

from core.timeutil import UTC

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.config import RedditConfig, Settings
from core.database import Base
from models.entities import RedditPost, Subreddit, TickerMention
from services.reddit.ingest_service import RedditIngestService
from services.reddit.types import RedditPostData

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="Set DATABASE_URL to run Postgres integration tests",
)


class MockRedditClient:
    def __init__(self, posts: list[RedditPostData]):
        self.posts = posts

    async def __aenter__(self) -> MockRedditClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def iter_posts(self, subreddit: str, sort: str, limit: int):
        for post in self.posts[:limit]:
            yield post

    async def fetch_comments(self, post_id: str, *, max_comments: int, min_score: int = 0):
        return []


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await session.merge(Subreddit(name="stocks", enabled=True))
        await session.commit()
        yield session
        await session.rollback()
    await engine.dispose()


@pytest.mark.asyncio
async def test_ingest_creates_post_and_mentions(db_session: AsyncSession):
    now = datetime.now(UTC)
    post = RedditPostData(
        id="t3_pytest_ingest",
        subreddit="stocks",
        author="trader1",
        created_utc=now,
        title="Bullish on $AAPL",
        body="Great DD",
        url=None,
        score=50,
        num_comments=2,
        flair="DD",
        permalink="https://reddit.com/r/stocks/t3_pytest_ingest",
    )
    settings = Settings(
        reddit=RedditConfig(
            subreddits=["stocks"],
            poll_sorts=["new"],
            max_posts_per_sub_per_poll=10,
            comment_fetch={"enabled": False},
        )
    )
    client = MockRedditClient([post])
    service = RedditIngestService(db_session, settings=settings, client=client)  # type: ignore[arg-type]
    stats = await service.ingest_all()
    await db_session.commit()

    assert stats.posts_fetched == 1
    assert stats.mentions_created >= 1
    post_row = await db_session.get(RedditPost, "t3_pytest_ingest")
    assert post_row is not None
    mentions = await db_session.execute(
        select(TickerMention).where(TickerMention.ticker == "AAPL")
    )
    assert mentions.scalars().first() is not None
