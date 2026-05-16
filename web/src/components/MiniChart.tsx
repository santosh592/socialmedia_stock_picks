import type { TickerDetailResponse } from "../types";

export default function MiniChart({ bars }: { bars: TickerDetailResponse["market_bars"] }) {
  if (!bars.length) {
    return <p className="empty" style={{ padding: "0.5rem 0" }}>No price data — add MARKET_API_KEY and re-ingest.</p>;
  }

  const closes = bars.map((b) => b.close);
  const min = Math.min(...closes);
  const max = Math.max(...closes);
  const range = max - min || 1;

  return (
    <div>
      <div className="chart-bars">
        {bars.map((b) => {
          const h = ((b.close - min) / range) * 100;
          return (
            <div
              key={b.date}
              className="chart-bar"
              style={{ height: `${Math.max(h, 4)}%` }}
              title={`${b.date}: $${b.close.toFixed(2)}`}
            />
          );
        })}
      </div>
      <p className="post-meta">
        {bars[0]?.date} → {bars[bars.length - 1]?.date}
      </p>
    </div>
  );
}
