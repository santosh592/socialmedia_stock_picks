from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from models.entities import IngestRun, Subreddit
from services.rollup.compute import RollupService
from services.opportunities.rules import OpportunityEngine


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
            # Reddit fetch will be implemented in services/reddit/
            run.posts_fetched = 0
            run.comments_fetched = 0
            run.mentions_created = 0

            if self.settings.aggregation.recompute_on_ingest:
                rollup = RollupService(self.db)
                await rollup.recompute_all()
                for profile in self.settings.ranking.profiles:
                    profile_cfg = self.settings.ranking.profiles[profile]
                    engine = OpportunityEngine(self.db)
                    await engine.evaluate(profile, profile_cfg.default_window)

            run.status = "success"
        except Exception as exc:
            run.status = "failed"
            run.errors = {"message": str(exc)}
            raise
        finally:
            run.finished_at = datetime.now(UTC)
            await self.db.commit()

        return run

    async def _ensure_subreddits(self) -> None:
        for name in self.settings.reddit.subreddits:
            stmt = (
                insert(Subreddit)
                .values(name=name, enabled=True, poll_sorts=self.settings.reddit.poll_sorts)
                .on_conflict_do_nothing(index_elements=["name"])
            )
            await self.db.execute(stmt)
