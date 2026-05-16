from __future__ import annotations

from datetime import datetime

from core.timeutil import UTC
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from models.entities import OpportunitySignal, Summary, TickerRollup


class DigestWorker:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.settings = get_settings()

    async def run(self) -> Path:
        digest_cfg = self.settings.digest
        output_dir = Path(digest_cfg.get("output_path", "data/digests"))
        if not output_dir.is_absolute():
            output_dir = Path(__file__).resolve().parents[2] / output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        window = digest_cfg.get("window", "24h")
        profile = digest_cfg.get("profile", "day")
        top_n = int(digest_cfg.get("top_n_tickers", 20))

        rollup_result = await self.db.execute(
            select(TickerRollup)
            .where(TickerRollup.window == window, TickerRollup.profile == profile)
            .order_by(TickerRollup.rank_score.desc())
            .limit(top_n)
        )
        rollups = list(rollup_result.scalars().all())

        lines = [
            "# Stock picks digest",
            "",
            f"Generated: {datetime.now(UTC).isoformat()}",
            f"Window: {window} · Profile: {profile}",
            "",
            "> Aggregates public social discussion for personal research. Not financial advice.",
            "",
            "## Top tickers",
            "",
        ]
        if not rollups:
            lines.append("_No rollup data yet — run ingest after configuring Reddit._")
        else:
            lines.append("| Rank | Ticker | Mentions | Velocity | |")
            lines.append("|------|--------|----------|----------|---|")
            for i, r in enumerate(rollups, 1):
                lines.append(
                    f"| {i} | {r.ticker} | {r.mention_count} | {r.velocity_pct:.0f}% | |"
                )
                summary_result = await self.db.execute(
                    select(Summary)
                    .where(Summary.ticker == r.ticker, Summary.window == window)
                    .order_by(Summary.created_at.desc())
                    .limit(1)
                )
                summary = summary_result.scalar_one_or_none()
                if summary and summary.payload.get("consensus"):
                    lines.append(f"\n**{r.ticker}:** {summary.payload['consensus'][:300]}")

        opp_result = await self.db.execute(
            select(OpportunitySignal)
            .where(OpportunitySignal.window == window, OpportunitySignal.profile == profile)
            .order_by(OpportunitySignal.score.desc())
            .limit(10)
        )
        opps = list(opp_result.scalars().all())
        lines.extend(["", "## Opportunities", ""])
        if not opps:
            lines.append("_None flagged._")
        else:
            for o in opps:
                lines.append(f"- **{o.type}** `{o.ticker}` — {o.hypothesis}")

        stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        path = output_dir / f"digest_{stamp}.md"
        path.write_text("\n".join(lines), encoding="utf-8")
        return path
