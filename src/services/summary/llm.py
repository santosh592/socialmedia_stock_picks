from __future__ import annotations

import hashlib
import logging
from datetime import datetime

from core.timeutil import UTC

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from models.entities import Summary
from services.market.tiingo import MarketDataService
from services.summary.context import SummaryContextBuilder
from services.summary.llm_providers import call_summary_llm
from services.summary.prompt import PROMPT_VERSION

logger = logging.getLogger(__name__)


class SummaryService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.settings = get_settings()
        self.context_builder = SummaryContextBuilder(db)
        self.market = MarketDataService(db, self.settings)

    def _cache_key(self, ticker: str, window: str, source_ids: list[str], window_end: str) -> str:
        content_version = hashlib.sha256(
            ("".join(sorted(source_ids)) + window_end).encode()
        ).hexdigest()[:16]
        return f"{ticker}:{window}:{content_version}"

    async def generate(self, ticker: str, window: str, *, force: bool = False) -> dict:
        context = await self.context_builder.build(
            ticker,
            window,
            top_posts=int(self.settings.llm.summaries.get("top_posts", 15)),
            top_comments=int(self.settings.llm.summaries.get("top_comments", 30)),
        )
        min_mentions = float(self.settings.llm.summaries.get("min_weighted_mentions", 5))

        if context is None:
            return self._insufficient_payload(ticker, window, "No mentions found in this window.")

        weighted = context["stats"].get("weighted_mentions", 0)
        if weighted < min_mentions:
            return self._insufficient_payload(
                ticker,
                window,
                f"Only {weighted:.1f} weighted mentions; need at least {min_mentions}.",
            )

        cache_key = self._cache_key(
            ticker,
            window,
            context["source_ids"],
            context["window_end"],
        )
        if not force:
            existing = await self.db.execute(select(Summary).where(Summary.cache_key == cache_key))
            row = existing.scalar_one_or_none()
            if row:
                return row.payload

        market_snippet = {
            "price_5d_pct": await self.market.price_5d_pct(ticker),
            "volume_vs_20d": await self.market.volume_vs_20d(ticker),
        }

        if not self.settings.llm.api_key:
            env_hint = (
                "GEMINI_API_KEY"
                if self.settings.llm.provider == "gemini"
                else "LLM_API_KEY"
            )
            payload = self._insufficient_payload(
                ticker, window, f"{env_hint} not configured."
            )
        else:
            try:
                payload = await self._call_llm(context, market_snippet)
            except Exception as exc:
                logger.exception("LLM summary failed for %s", ticker)
                payload = {
                    **self._insufficient_payload(ticker, window, str(exc)),
                    "status": "error",
                }

        summary = Summary(
            ticker=ticker,
            window=window,
            window_end=datetime.fromisoformat(context["window_end"]),
            payload=payload,
            model=self.settings.llm.model,
            prompt_version=PROMPT_VERSION,
            cache_key=cache_key,
        )
        self.db.add(summary)
        await self.db.commit()
        return payload

    async def _call_llm(self, context: dict, market_snippet: dict) -> dict:
        return await call_summary_llm(
            provider=self.settings.llm.provider,
            api_key=self.settings.llm.api_key,
            model=self.settings.llm.model,
            temperature=self.settings.llm.temperature,
            context=context,
            market_snippet=market_snippet,
        )

    def _insufficient_payload(self, ticker: str, window: str, reason: str) -> dict:
        return {
            "$schema": PROMPT_VERSION,
            "ticker": ticker,
            "window": window,
            "as_of": datetime.now(UTC).isoformat(),
            "status": "insufficient_discussion",
            "tone": None,
            "bull_points": [],
            "bear_points": [],
            "catalysts": [],
            "risks": [],
            "consensus": reason,
            "controversy": None,
            "citations": [],
            "disclaimer": "AI-generated summary of public posts; not financial advice.",
        }
