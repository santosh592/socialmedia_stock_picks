#!/usr/bin/env python3
"""Download NASDAQ-listed symbols into data/us_symbols.csv."""

from __future__ import annotations

import csv
from pathlib import Path

import httpx

NASDAQ_URL = "https://api.nasdaq.com/api/screener/stocks?tableonly=true&limit=10000&download=true"
OUTPUT = Path(__file__).resolve().parents[1] / "data" / "us_symbols.csv"


def main() -> None:
    headers = {"User-Agent": "socialmedia_stock_picks/0.1"}
    response = httpx.get(NASDAQ_URL, headers=headers, timeout=60.0)
    response.raise_for_status()
    data = response.json()
    rows = data.get("data", {}).get("rows", []) or data.get("data", {}).get("table", {}).get("rows", [])
    symbols: set[str] = set()
    for row in rows:
        sym = (row.get("symbol") or "").strip().upper()
        if sym and sym.isalpha() or "." in sym:
            symbols.add(sym.replace("-", "."))
    symbols = {s for s in symbols if 1 <= len(s) <= 5}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["symbol"])
        for sym in sorted(symbols):
            writer.writerow([sym])
    print(f"Wrote {len(symbols)} symbols to {OUTPUT}")


if __name__ == "__main__":
    main()
