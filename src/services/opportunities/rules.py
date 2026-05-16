from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from models.entities import OpportunitySignal, TickerRollup
from services.market.tiingo import MarketDataService


class OpportunityEngine:
    """Evaluates watchlist-style opportunity rules (O1–O6)."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.settings = get_settings()
        self.market = MarketDataService(db, self.settings)

    async def evaluate(self, profile: str, window: str) -> int:
        enabled = set(self.settings.opportunities.get("enabled_types", []))
        result = await self.db.execute(
            select(TickerRollup).where(
                TickerRollup.profile == profile,
                TickerRollup.window == window,
            )
        )
        rollups = result.scalars().all()
        if not rollups:
            return 0
        window_end = rollups[0].window_end
        await self.db.execute(
            delete(OpportunitySignal).where(
                OpportunitySignal.profile == profile,
                OpportunitySignal.window == window,
                OpportunitySignal.window_end == window_end,
            )
        )
        created = 0
        for rollup in rollups:
            price_5d = await self.market.price_5d_pct(rollup.ticker)
            if "O1" in enabled:
                created += await self._maybe_o1(rollup, window_end, profile, price_5d)
            if "O2" in enabled:
                created += await self._maybe_o2(rollup, window_end, profile, price_5d)
            if "O3" in enabled and window == "7d":
                created += await self._maybe_o3(rollup, window_end, profile)
            if "O5" in enabled:
                created += await self._maybe_o5(rollup, window_end, profile, price_5d)
        await self.db.commit()
        return created

    async def _maybe_o1(
        self,
        rollup: TickerRollup,
        window_end: datetime,
        profile: str,
        price_5d: float | None,
    ) -> int:
        cfg = self.settings.opportunities.get("O1", {})
        if rollup.velocity_pct < cfg.get("velocity_z_min", 2.0) * 10:
            return 0
        max_price = cfg.get("price_5d_abs_max_pct", 3.0)
        if price_5d is not None and abs(price_5d) > max_price:
            return 0
        self.db.add(
            OpportunitySignal(
                ticker=rollup.ticker,
                type="O1",
                window=rollup.window,
                window_end=window_end,
                profile=profile,
                score=min(1.0, rollup.velocity_pct / 100.0),
                confidence="medium" if rollup.velocity_pct > 50 else "low",
                hypothesis="Elevated mention velocity while 5d price change is relatively flat.",
                inputs={
                    "velocity_pct": rollup.velocity_pct,
                    "price_5d_pct": price_5d,
                    "weighted_mentions": rollup.weighted_mentions,
                },
            )
        )
        return 1

    async def _maybe_o2(
        self,
        rollup: TickerRollup,
        window_end: datetime,
        profile: str,
        price_5d: float | None,
    ) -> int:
        cfg = self.settings.opportunities.get("O2", {})
        if rollup.velocity_pct < cfg.get("velocity_min_pct", 50):
            return 0
        min_price = cfg.get("price_5d_min_pct", 8.0)
        if price_5d is None or price_5d < min_price:
            return 0
        self.db.add(
            OpportunitySignal(
                ticker=rollup.ticker,
                type="O2",
                window=rollup.window,
                window_end=window_end,
                profile=profile,
                score=min(1.0, rollup.velocity_pct / 150.0),
                confidence="medium",
                hypothesis="Rising mentions alongside a strong 5d price move — may be crowded.",
                inputs={"velocity_pct": rollup.velocity_pct, "price_5d_pct": price_5d},
            )
        )
        return 1

    async def _maybe_o3(self, rollup: TickerRollup, window_end: datetime, profile: str) -> int:
        intents = rollup.intent_counts or {}
        bullish = intents.get("dd", 0) + intents.get("earnings", 0)
        yolo = intents.get("yolo", 0)
        total = max(sum(intents.values()), 1)
        bullish_pct = (bullish / total) * 100
        if bullish_pct > 40:
            return 0
        self.db.add(
            OpportunitySignal(
                ticker=rollup.ticker,
                type="O3",
                window=rollup.window,
                window_end=window_end,
                profile=profile,
                score=0.5,
                confidence="low",
                hypothesis="Constructive intent share appears low vs hype — possible narrative shift.",
                inputs={"intent_counts": intents, "bullish_pct": bullish_pct},
            )
        )
        return 1

    async def _maybe_o5(
        self,
        rollup: TickerRollup,
        window_end: datetime,
        profile: str,
        price_5d: float | None,
    ) -> int:
        cfg = self.settings.opportunities.get("O5", {})
        intents = rollup.intent_counts or {}
        dd_count = intents.get("dd", 0)
        if dd_count < cfg.get("dd_post_min", 2):
            return 0
        max_price = cfg.get("price_5d_abs_max_pct", 4.0)
        if price_5d is not None and abs(price_5d) > max_price:
            return 0
        if rollup.engagement_depth < cfg.get("min_comments", 20):
            return 0
        self.db.add(
            OpportunitySignal(
                ticker=rollup.ticker,
                type="O5",
                window=rollup.window,
                window_end=window_end,
                profile=profile,
                score=0.6,
                confidence="medium",
                hypothesis="Multiple DD-style posts with solid engagement while price is muted.",
                inputs={
                    "dd_posts": dd_count,
                    "engagement_depth": rollup.engagement_depth,
                    "price_5d_pct": price_5d,
                },
            )
        )
        return 1
