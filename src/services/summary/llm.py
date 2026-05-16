from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from models.entities import Summary


class SummaryService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.settings = get_settings()

    def _cache_key(self, ticker: str, window: str) -> str:
        raw = f"{ticker}:{window}:{datetime.now(UTC).date().isoformat()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    async def generate(self, ticker: str, window: str, *, force: bool = False) -> dict:
        cache_key = self._cache_key(ticker, window)
        if not force:
            existing = await self.db.execute(select(Summary).where(Summary.cache_key == cache_key))
            row = existing.scalar_one_or_none()
            if row:
                return row.payload

        # Placeholder until Reddit + LLM wiring is implemented
        payload = {
            "$schema": "summary_v1",
            "ticker": ticker,
            "window": window,
            "as_of": datetime.now(UTC).isoformat(),
            "status": "insufficient_discussion",
            "tone": None,
            "bull_points": [],
            "bear_points": [],
            "catalysts": [],
            "risks": [],
            "consensus": "No discussion ingested yet. Run ingest after configuring Reddit API credentials.",
            "controversy": None,
            "citations": [],
            "disclaimer": "AI-generated summary of public posts; not financial advice.",
        }
        summary = Summary(
            ticker=ticker,
            window=window,
            window_end=datetime.now(UTC),
            payload=payload,
            model=self.settings.llm.model,
            prompt_version="summary_v1",
            cache_key=cache_key,
        )
        self.db.add(summary)
        await self.db.commit()
        return payload
