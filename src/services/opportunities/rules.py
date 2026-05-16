from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from models.entities import OpportunitySignal, TickerRollup


class OpportunityEngine:
    """Evaluates watchlist-style opportunity rules (O1–O6)."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.settings = get_settings()

    async def evaluate(self, profile: str, window: str) -> int:
        enabled = set(self.settings.opportunities.get("enabled_types", []))
        result = await self.db.execute(
            select(TickerRollup).where(
                TickerRollup.profile == profile,
                TickerRollup.window == window,
            )
        )
        rollups = result.scalars().all()
        created = 0
        window_end = rollups[0].window_end if rollups else datetime.now(UTC)
        for rollup in rollups:
            if "O1" in enabled:
                created += await self._maybe_o1(rollup, window_end, profile)
            if "O2" in enabled:
                created += await self._maybe_o2(rollup, window_end, profile)
        await self.db.commit()
        return created

    async def _maybe_o1(self, rollup: TickerRollup, window_end: datetime, profile: str) -> int:
        cfg = self.settings.opportunities.get("O1", {})
        if rollup.velocity_pct < cfg.get("velocity_z_min", 2.0) * 10:
            return 0
        signal = OpportunitySignal(
            ticker=rollup.ticker,
            type="O1",
            window=rollup.window,
            window_end=window_end,
            profile=profile,
            score=min(1.0, rollup.velocity_pct / 100.0),
            confidence="medium" if rollup.velocity_pct > 50 else "low",
            hypothesis="Elevated mention velocity while price has not moved sharply (social lead).",
            inputs={"velocity_pct": rollup.velocity_pct, "weighted_mentions": rollup.weighted_mentions},
        )
        self.db.add(signal)
        return 1

    async def _maybe_o2(self, rollup: TickerRollup, window_end: datetime, profile: str) -> int:
        cfg = self.settings.opportunities.get("O2", {})
        if rollup.velocity_pct < cfg.get("velocity_min_pct", 50):
            return 0
        signal = OpportunitySignal(
            ticker=rollup.ticker,
            type="O2",
            window=rollup.window,
            window_end=window_end,
            profile=profile,
            score=min(1.0, rollup.velocity_pct / 150.0),
            confidence="low",
            hypothesis="Rising mentions may indicate a crowded move; verify price action.",
            inputs={"velocity_pct": rollup.velocity_pct},
        )
        self.db.add(signal)
        return 1
