from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings


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

        stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        path = output_dir / f"digest_{stamp}.md"
        window = digest_cfg.get("window", "24h")
        profile = digest_cfg.get("profile", "day")
        content = f"""# Stock picks digest

Generated: {datetime.now(UTC).isoformat()}
Window: {window}
Profile: {profile}

> Aggregates public social discussion for personal research. Not financial advice.

_No tickers yet — run ingest after Reddit API is configured._
"""
        path.write_text(content, encoding="utf-8")
        return path
