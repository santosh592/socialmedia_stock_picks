import { Link } from "react-router-dom";
import type { OpportunityCard } from "../types";

export default function OpportunityGrid({
  items,
  window,
  profile = "day",
}: {
  items: OpportunityCard[];
  window: string;
  profile?: string;
}) {
  if (items.length === 0) return null;

  return (
    <section>
      <h2 className="section-title">Watchlist signals</h2>
      <div className="opportunity-grid">
        {items.map((o) => (
          <article key={`${o.type}-${o.ticker}`} className="opp-card">
            <header>
              <span className="opp-type">{o.type}</span>
              <span className={`badge ${o.confidence}`}>{o.confidence}</span>
            </header>
            <Link to={`/ticker/${o.ticker}?window=${window}&profile=${profile}`} className="opp-ticker">
              {o.ticker}
            </Link>
            <p className="opp-hypothesis">{o.hypothesis}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
