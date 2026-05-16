from __future__ import annotations

import csv
import re
from functools import lru_cache
from pathlib import Path

from core.config import Settings, get_settings

CASHTAG_RE = re.compile(r"\$([A-Z]{1,5})\b")
WORD_RE = re.compile(r"\b([A-Z]{1,5})\b")
BRK_RE = re.compile(r"\bBRK-([AB])\b")


@lru_cache
def _load_allowlist(path: str) -> frozenset[str]:
    symbols: set[str] = set()
    with Path(path).open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sym = row.get("symbol") or row.get("Symbol") or next(iter(row.values()), "")
            if sym:
                symbols.add(sym.strip().upper())
    return frozenset(symbols)


class TickerExtractor:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.blocklist = {s.upper() for s in self.settings.ticker_extraction.blocklist}
        self.allowlist = _load_allowlist(str(self.settings.allowlist_path))

    def extract(self, text: str) -> list[str]:
        if not text:
            return []
        normalized = text.upper()
        normalized = BRK_RE.sub(r"BRK.\1", normalized)
        candidates: set[str] = set()
        for match in CASHTAG_RE.finditer(normalized):
            candidates.add(match.group(1))
        for match in WORD_RE.finditer(normalized):
            candidates.add(match.group(1))
        return [
            t
            for t in candidates
            if t not in self.blocklist and t in self.allowlist
        ]

    def weight_for(
        self,
        location: str,
        *,
        dd_flair: bool = False,
        negative_score: bool = False,
    ) -> float:
        weights = self.settings.ticker_extraction.weights
        base = weights.get(location, weights.get("post_body", 1.0))
        if dd_flair:
            base *= weights.get("dd_flair", 1.3)
        if negative_score:
            base *= weights.get("negative_score_multiplier", 0.5)
        return base
