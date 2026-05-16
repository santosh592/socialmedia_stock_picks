from __future__ import annotations

import logging
from datetime import date, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import Settings, get_settings
from models.entities import MarketBar, TickerRollup

logger = logging.getLogger(__name__)

TIINGO_DAILY_URL = "https://api.tiingo.com/tiingo/daily/{ticker}/prices"


class MarketDataService:
    def __init__(self, db: AsyncSession, settings: Settings | None = None) -> None:
        self.db = db
        self.settings = settings or get_settings()
        self.api_key = self.settings.market.get("api_key", "")
        self.lookback_days = int(self.settings.market.get("daily_bars_lookback_days", 60))

    async def sync_active_tickers(self) -> int:
        if not self.api_key:
            logger.warning("MARKET_API_KEY not set; skipping market sync")
            return 0
        tickers = await self._active_tickers()
        synced = 0
        for ticker in tickers:
            try:
                synced += await self.sync_ticker(ticker)
            except Exception as exc:
                logger.warning("Market sync failed for %s: %s", ticker, exc)
        await self.db.commit()
        return synced

    async def _active_tickers(self) -> list[str]:
        result = await self.db.execute(select(TickerRollup.ticker).distinct())
        return [row[0] for row in result.all()]

    async def sync_ticker(self, ticker: str) -> int:
        end = date.today()
        start = end - timedelta(days=self.lookback_days)
        bars = await self._fetch_tiingo_daily(ticker, start, end)
        if not bars:
            return 0
        for bar in bars:
            stmt = (
                insert(MarketBar)
                .values(
                    ticker=ticker,
                    date=bar["date"],
                    open=bar["open"],
                    high=bar["high"],
                    low=bar["low"],
                    close=bar["close"],
                    volume=int(bar["volume"]),
                )
                .on_conflict_do_update(
                    index_elements=["ticker", "date"],
                    set_={
                        "open": bar["open"],
                        "high": bar["high"],
                        "low": bar["low"],
                        "close": bar["close"],
                        "volume": int(bar["volume"]),
                    },
                )
            )
            await self.db.execute(stmt)
        return len(bars)

    async def _fetch_tiingo_daily(self, ticker: str, start: date, end: date) -> list[dict]:
        params = {
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "token": self.api_key,
        }
        url = TIINGO_DAILY_URL.format(ticker=ticker)
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params)
            if response.status_code == 404:
                return []
            response.raise_for_status()
            rows = response.json()
        bars = []
        for row in rows:
            bars.append(
                {
                    "date": date.fromisoformat(row["date"][:10]),
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row.get("volume", 0)),
                }
            )
        return bars

    async def price_5d_pct(self, ticker: str) -> float | None:
        result = await self.db.execute(
            select(MarketBar)
            .where(MarketBar.ticker == ticker)
            .order_by(MarketBar.date.desc())
            .limit(6)
        )
        bars = list(result.scalars().all())
        if len(bars) < 2:
            return None
        latest = bars[0].close
        ref = bars[min(5, len(bars) - 1)].close
        if ref == 0:
            return None
        return round(((latest - ref) / ref) * 100.0, 2)

    async def volume_vs_20d(self, ticker: str) -> float | None:
        result = await self.db.execute(
            select(MarketBar)
            .where(MarketBar.ticker == ticker)
            .order_by(MarketBar.date.desc())
            .limit(21)
        )
        bars = list(result.scalars().all())
        if len(bars) < 2:
            return None
        avg_vol = sum(b.volume for b in bars[1:]) / max(len(bars) - 1, 1)
        if avg_vol == 0:
            return None
        return round(bars[0].volume / avg_vol, 2)
