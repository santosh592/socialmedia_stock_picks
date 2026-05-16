"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-05-16

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "subreddits",
        sa.Column("name", sa.String(64), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("poll_sorts", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "ingest_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("posts_fetched", sa.Integer(), server_default="0"),
        sa.Column("comments_fetched", sa.Integer(), server_default="0"),
        sa.Column("mentions_created", sa.Integer(), server_default="0"),
        sa.Column("errors", postgresql.JSONB(), nullable=True),
    )
    op.create_table(
        "reddit_posts",
        sa.Column("id", sa.String(16), primary_key=True),
        sa.Column("subreddit", sa.String(64), sa.ForeignKey("subreddits.name"), nullable=False),
        sa.Column("author", sa.String(64), nullable=False),
        sa.Column("created_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("score", sa.Integer(), server_default="0"),
        sa.Column("num_comments", sa.Integer(), server_default="0"),
        sa.Column("flair", sa.String(128), nullable=True),
        sa.Column("permalink", sa.Text(), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_reddit_posts_sub_created", "reddit_posts", ["subreddit", "created_utc"])
    op.create_index("ix_reddit_posts_created", "reddit_posts", ["created_utc"])

    op.create_table(
        "reddit_comments",
        sa.Column("id", sa.String(16), primary_key=True),
        sa.Column("post_id", sa.String(16), sa.ForeignKey("reddit_posts.id"), nullable=False),
        sa.Column("parent_id", sa.String(16), nullable=True),
        sa.Column("author", sa.String(64), nullable=False),
        sa.Column("created_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("score", sa.Integer(), server_default="0"),
        sa.Column("permalink", sa.Text(), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_reddit_comments_post_created", "reddit_comments", ["post_id", "created_utc"])

    op.create_table(
        "post_intents",
        sa.Column("post_id", sa.String(16), sa.ForeignKey("reddit_posts.id"), primary_key=True),
        sa.Column("intent", sa.String(32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("classified_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "ticker_mentions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("ticker", sa.String(16), nullable=False),
        sa.Column("source_type", sa.String(8), nullable=False),
        sa.Column("source_id", sa.String(16), nullable=False),
        sa.Column("subreddit", sa.String(64), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("location", sa.String(16), nullable=False),
        sa.Column("created_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("ticker", "source_type", "source_id", name="uq_mention_source"),
    )
    op.create_index("ix_ticker_mentions_ticker_created", "ticker_mentions", ["ticker", "created_utc"])
    op.create_index("ix_ticker_mentions_created", "ticker_mentions", ["created_utc"])

    op.create_table(
        "ticker_rollups",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("ticker", sa.String(16), nullable=False),
        sa.Column("window", sa.String(8), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("mention_count", sa.Integer(), server_default="0"),
        sa.Column("weighted_mentions", sa.Float(), server_default="0"),
        sa.Column("unique_authors", sa.Integer(), server_default="0"),
        sa.Column("velocity_pct", sa.Float(), server_default="0"),
        sa.Column("engagement_depth", sa.Float(), server_default="0"),
        sa.Column("subreddit_breadth", sa.Integer(), server_default="0"),
        sa.Column("intent_counts", postgresql.JSONB(), nullable=True),
        sa.Column("rank_score", sa.Float(), server_default="0"),
        sa.Column("profile", sa.String(8), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("ticker", "window", "window_end", "profile", name="uq_rollup"),
    )
    op.create_index(
        "ix_ticker_rollups_window_rank",
        "ticker_rollups",
        ["window", "window_end", "profile", "rank_score"],
    )

    op.create_table(
        "market_bars",
        sa.Column("ticker", sa.String(16), primary_key=True),
        sa.Column("date", sa.Date(), primary_key=True),
        sa.Column("open", sa.Float(), nullable=False),
        sa.Column("high", sa.Float(), nullable=False),
        sa.Column("low", sa.Float(), nullable=False),
        sa.Column("close", sa.Float(), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=False),
    )
    op.create_table(
        "summaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ticker", sa.String(16), nullable=False),
        sa.Column("window", sa.String(8), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("model", sa.String(64), nullable=False),
        sa.Column("prompt_version", sa.String(16), nullable=False),
        sa.Column("cache_key", sa.String(128), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_summaries_ticker", "summaries", ["ticker"])

    op.create_table(
        "opportunity_signals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ticker", sa.String(16), nullable=False),
        sa.Column("type", sa.String(4), nullable=False),
        sa.Column("window", sa.String(8), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("profile", sa.String(8), nullable=False),
        sa.Column("score", sa.Float(), server_default="0"),
        sa.Column("confidence", sa.String(8), nullable=False),
        sa.Column("hypothesis", sa.Text(), nullable=False),
        sa.Column("inputs", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_opportunity_signals_window",
        "opportunity_signals",
        ["window_end", "profile", "type", "score"],
    )

    op.create_table(
        "app_config",
        sa.Column("key", sa.String(128), primary_key=True),
        sa.Column("value", postgresql.JSONB(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("app_config")
    op.drop_table("opportunity_signals")
    op.drop_table("summaries")
    op.drop_table("market_bars")
    op.drop_table("ticker_rollups")
    op.drop_table("ticker_mentions")
    op.drop_table("post_intents")
    op.drop_table("reddit_comments")
    op.drop_table("reddit_posts")
    op.drop_table("ingest_runs")
    op.drop_table("subreddits")
