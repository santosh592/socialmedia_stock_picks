import { useCallback, useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { fetchTicker, summarizeTicker } from "../api/client";
import MiniChart from "../components/MiniChart";
import SummaryPanel from "../components/SummaryPanel";
import type { Profile, SummaryPayload, TickerDetailResponse } from "../types";
import { formatNum, formatPct } from "../utils/format";

export default function TickerPage() {
  const { symbol = "" } = useParams();
  const [searchParams] = useSearchParams();
  const window = searchParams.get("window") ?? "7d";
  const profile = (searchParams.get("profile") ?? "swing") as Profile;

  const [data, setData] = useState<TickerDetailResponse | null>(null);
  const [summary, setSummary] = useState<SummaryPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchTicker(symbol.toUpperCase(), window, profile);
      setData(res);
      setSummary(res.summary);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load ticker");
    } finally {
      setLoading(false);
    }
  }, [symbol, window, profile]);

  useEffect(() => {
    load();
  }, [load]);

  const handleSummarize = async (force = false) => {
    setGenerating(true);
    try {
      const res = await summarizeTicker(symbol.toUpperCase(), window, force);
      setSummary(res.summary);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Summary failed");
    } finally {
      setGenerating(false);
    }
  };

  if (loading && !data) {
    return <p className="loading">Loading {symbol}…</p>;
  }

  return (
    <>
      <Link to={`/?window=${window}&profile=${profile}`} className="back-link">
        ← Back to dashboard
      </Link>

      {error && <div className="error-banner">{error}</div>}

      <header className="header" style={{ marginBottom: "1.25rem" }}>
        <div>
          <h1 style={{ fontFamily: "var(--mono)" }}>{symbol.toUpperCase()}</h1>
          <p>
            {window} window · {profile} profile
          </p>
        </div>
      </header>

      {data && (
        <div className="detail-grid">
          <div className="card">
            <h2 className="section-title">Discussion stats</h2>
            <div className="stat-row">
              <div className="stat">
                <label>Mentions</label>
                <span className="stat-value">{formatNum(data.rollup.mention_count)}</span>
              </div>
              <div className="stat">
                <label>Authors</label>
                <span className="stat-value">{formatNum(data.rollup.unique_authors)}</span>
              </div>
              <div className="stat">
                <label>Velocity</label>
                <span className="stat-value">{formatPct(data.rollup.velocity_pct, 0)}</span>
              </div>
              <div className="stat">
                <label>Rank score</label>
                <span className="stat-value">{data.rollup.rank_score.toFixed(1)}</span>
              </div>
            </div>
            {data.rollup.intent_counts && (
              <p className="post-meta" style={{ marginTop: "1rem" }}>
                Intents:{" "}
                {Object.entries(data.rollup.intent_counts)
                  .map(([k, v]) => `${k} (${v})`)
                  .join(", ")}
              </p>
            )}
          </div>

          <div className="card">
            <h2 className="section-title">Price (daily)</h2>
            <MiniChart bars={data.market_bars} />
          </div>

          {data.opportunities.length > 0 && (
            <div className="card span-full">
              <h2 className="section-title">Signals for this ticker</h2>
              <ul className="post-list">
                {data.opportunities.map((o) => (
                  <li key={o.type}>
                    <strong>{o.type}</strong> ({o.confidence}) — {o.hypothesis}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {data.top_posts.length > 0 && (
            <div className="card span-full">
              <h2 className="section-title">Top Reddit threads</h2>
              <ul className="post-list">
                {data.top_posts.map((p) => (
                  <li key={p.id}>
                    <a href={p.permalink} target="_blank" rel="noreferrer">
                      {p.title}
                    </a>
                    <div className="post-meta">
                      r/{p.subreddit} · {p.score} pts
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <SummaryPanel
            summary={summary}
            onGenerate={() => handleSummarize(!!summary)}
            generating={generating}
          />
        </div>
      )}
    </>
  );
}
