from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from core.config import Settings
from core.database import async_session_factory
from workers.digest import DigestWorker
from workers.ingest import IngestWorker

logger = logging.getLogger(__name__)


def start_scheduler(settings: Settings) -> AsyncIOScheduler | None:
    if settings.ingest.mode != "scheduled":
        logger.info("Ingest scheduler disabled (mode=%s)", settings.ingest.mode)
        return None

    scheduler = AsyncIOScheduler()

    async def ingest_job() -> None:
        async with async_session_factory() as db:
            worker = IngestWorker(db)
            await worker.run()

    async def digest_job() -> None:
        if not settings.digest.get("enabled", False):
            return
        async with async_session_factory() as db:
            worker = DigestWorker(db)
            await worker.run()

    scheduler.add_job(
        ingest_job,
        IntervalTrigger(minutes=settings.ingest.interval_minutes),
        id="ingest",
        replace_existing=True,
    )
    if settings.digest.get("enabled", False):
        scheduler.add_job(digest_job, IntervalTrigger(hours=24), id="digest", replace_existing=True)

    scheduler.start()
    logger.info("Scheduler started (ingest every %sm)", settings.ingest.interval_minutes)
    return scheduler


def stop_scheduler(scheduler: AsyncIOScheduler | None) -> None:
    if scheduler:
        scheduler.shutdown(wait=False)
