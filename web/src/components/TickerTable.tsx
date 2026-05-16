import { useNavigate } from "react-router-dom";
import type { TickerRow } from "../types";
import { formatNum, formatPct } from "../utils/format";

interface TickerTableProps {
  rows: TickerRow[];
  window: string;
  profile: string;
}

export default function TickerTable({ rows, window, profile }: TickerTableProps) {
  const navigate = useNavigate();

  if (rows.length === 0) {
    return (
      <div className="card empty">
        No tickers yet. Configure Reddit credentials and run ingest.
      </div>
    );
  }

  return (
    <section>
      <h2 className="section-title">Most discussed</h2>
      <div className="card table-wrap">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Ticker</th>
              <th>Mentions</th>
              <th>Authors</th>
              <th>Velocity</th>
              <th>5d %</th>
              <th>Tone</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={row.ticker}
                className="clickable"
                onClick={() =>
                  navigate(`/ticker/${row.ticker}?window=${window}&profile=${profile}`)
                }
              >
                <td>{row.rank}</td>
                <td className="ticker-link">{row.ticker}</td>
                <td>{formatNum(row.mention_count)}</td>
                <td>{formatNum(row.unique_authors)}</td>
                <td
                  className={
                    row.velocity_pct > 0 ? "num-positive" : row.velocity_pct < 0 ? "num-negative" : ""
                  }
                >
                  {formatPct(row.velocity_pct, 0)}
                </td>
                <td
                  className={
                    (row.price_5d_pct ?? 0) > 0
                      ? "num-positive"
                      : (row.price_5d_pct ?? 0) < 0
                        ? "num-negative"
                        : ""
                  }
                >
                  {formatPct(row.price_5d_pct)}
                </td>
                <td>{row.summary_tone ?? (row.has_summary ? "…" : "—")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
