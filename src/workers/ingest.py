from __future__ import annotations

import logging
from datetime import datetime

from core.timeutil import UTC

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from models.entities import IngestRun, Subreddit
from services.market.tiingo import MarketDataService
from services.opportunities.rules import OpportunityEngine
from services.reddit.ingest_service import RedditIngestService
from services.rollup.compute import RollupService

logger = logging.getLogger(__name__)


class IngestWorker:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.settings = get_settings()

    async def run(self) -> IngestRun:
        run = IngestRun(status="running", started_at=datetime.now(UTC))
        self.db.add(run)
        await self.db.flush()

        try:
            await self._ensure_subreddits()
            reddit_stats = await self._run_reddit_ingest()
            run.posts_fetched = reddit_stats.posts_fetched
            run.comments_fetched = reddit_stats.comments_fetched
            run.mentions_created = reddit_stats.mentions_created
            if reddit_stats.errors:
                run.errors = {"subreddit_errors": reddit_stats.errors}

            if self.settings.aggregation.recompute_on_ingest:
                rollup = RollupService(self.db)
                await rollup.recompute_all()

                if self.settings.market.get("sync_on_rollup", True):
                    market = MarketDataService(self.db)
                    await market.sync_active_tickers()

                for profile in self.settings.ranking.profiles:
                    profile_cfg = self.settings.ranking.profiles[profile]
                    engine = OpportunityEngine(self.db)
                    await engine.evaluate(profile, profile_cfg.default_window)

            run.status = "success"
        except Exception as exc:
            run.status = "failed"
            run.errors = {"message": str(exc)}
            logger.exception("Ingest failed")
            raise
        finally:
            run.finished_at = datetime.now(UTC)
            await self.db.commit()

        return run

    async def _run_reddit_ingest(self):
        settings = self.settings
        if not all(
            [
                settings.reddit.client_id,
                settings.reddit.client_secret,
                settings.reddit.username,
                settings.reddit.password,
            ]
        ):
            from services.reddit.types import IngestStats

            logger.warning("Reddit credentials missing; skipping Reddit fetch")
            return IngestStats(
                errors=["Reddit credentials not configured in .env"],
            )
        service = RedditIngestService(self.db)
        return await service.ingest_all()

    async def _ensure_subreddits(self) -> None:
        for name in self.settings.reddit.subreddits:
            stmt = (
                insert(Subreddit)
                .values(name=name, enabled=True, poll_sorts=self.settings.reddit.poll_sorts)
                .on_conflict_do_nothing(index_elements=["name"])
            )
            await self.db.execute(stmt)
