from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


class Subreddit(Base):
    __tablename__ = "subreddits"

    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    poll_sorts: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    posts: Mapped[list[RedditPost]] = relationship(back_populates="subreddit_rel")


class IngestRun(Base):
    __tablename__ = "ingest_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="running")
    posts_fetched: Mapped[int] = mapped_column(Integer, default=0)
    comments_fetched: Mapped[int] = mapped_column(Integer, default=0)
    mentions_created: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)


class RedditPost(Base):
    __tablename__ = "reddit_posts"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    subreddit: Mapped[str] = mapped_column(String(64), ForeignKey("subreddits.name"))
    author: Mapped[str] = mapped_column(String(64))
    created_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    title: Mapped[str] = mapped_column(Text)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[int] = mapped_column(Integer, default=0)
    num_comments: Mapped[int] = mapped_column(Integer, default=0)
    flair: Mapped[str | None] = mapped_column(String(128), nullable=True)
    permalink: Mapped[str] = mapped_column(Text)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    subreddit_rel: Mapped[Subreddit] = relationship(back_populates="posts")
    comments: Mapped[list[RedditComment]] = relationship(back_populates="post")
    intent: Mapped[PostIntent | None] = relationship(back_populates="post", uselist=False)


class RedditComment(Base):
    __tablename__ = "reddit_comments"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    post_id: Mapped[str] = mapped_column(String(16), ForeignKey("reddit_posts.id"))
    parent_id: Mapped[str | None] = mapped_column(String(16), nullable=True)
    author: Mapped[str] = mapped_column(String(64))
    created_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    body: Mapped[str] = mapped_column(Text)
    score: Mapped[int] = mapped_column(Integer, default=0)
    permalink: Mapped[str] = mapped_column(Text)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    post: Mapped[RedditPost] = relationship(back_populates="comments")


class PostIntent(Base):
    __tablename__ = "post_intents"

    post_id: Mapped[str] = mapped_column(String(16), ForeignKey("reddit_posts.id"), primary_key=True)
    intent: Mapped[str] = mapped_column(String(32))
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    classified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    post: Mapped[RedditPost] = relationship(back_populates="intent")


class TickerMention(Base):
    __tablename__ = "ticker_mentions"
    __table_args__ = (
        UniqueConstraint("ticker", "source_type", "source_id", name="uq_mention_source"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(16), index=True)
    source_type: Mapped[str] = mapped_column(String(8))
    source_id: Mapped[str] = mapped_column(String(16))
    subreddit: Mapped[str] = mapped_column(String(64))
    weight: Mapped[float] = mapped_column(Float)
    location: Mapped[str] = mapped_column(String(16))
    created_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TickerRollup(Base):
    __tablename__ = "ticker_rollups"
    __table_args__ = (
        UniqueConstraint("ticker", "window", "window_end", "profile", name="uq_rollup"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(16), index=True)
    window: Mapped[str] = mapped_column(String(8))
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    mention_count: Mapped[int] = mapped_column(Integer, default=0)
    weighted_mentions: Mapped[float] = mapped_column(Float, default=0.0)
    unique_authors: Mapped[int] = mapped_column(Integer, default=0)
    velocity_pct: Mapped[float] = mapped_column(Float, default=0.0)
    engagement_depth: Mapped[float] = mapped_column(Float, default=0.0)
    subreddit_breadth: Mapped[int] = mapped_column(Integer, default=0)
    intent_counts: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    rank_score: Mapped[float] = mapped_column(Float, default=0.0)
    profile: Mapped[str] = mapped_column(String(8))
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MarketBar(Base):
    __tablename__ = "market_bars"

    ticker: Mapped[str] = mapped_column(String(16), primary_key=True)
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[int] = mapped_column(BigInteger)


class Summary(Base):
    __tablename__ = "summaries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticker: Mapped[str] = mapped_column(String(16), index=True)
    window: Mapped[str] = mapped_column(String(8))
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict] = mapped_column(JSONB)
    model: Mapped[str] = mapped_column(String(64))
    prompt_version: Mapped[str] = mapped_column(String(16), default="summary_v1")
    cache_key: Mapped[str] = mapped_column(String(128), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OpportunitySignal(Base):
    __tablename__ = "opportunity_signals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticker: Mapped[str] = mapped_column(String(16), index=True)
    type: Mapped[str] = mapped_column(String(4))
    window: Mapped[str] = mapped_column(String(8))
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    profile: Mapped[str] = mapped_column(String(8))
    score: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[str] = mapped_column(String(8))
    hypothesis: Mapped[str] = mapped_column(Text)
    inputs: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AppConfigRow(Base):
    __tablename__ = "app_config"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
