import { Link } from "react-router-dom";

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="app-shell">
      <header className="header">
        <div>
          <Link to="/" style={{ color: "inherit", textDecoration: "none" }}>
            <h1>Stock Radar</h1>
          </Link>
          <p>Reddit discussion → ranked tickers → AI summaries</p>
        </div>
      </header>
      {children}
      <p className="disclaimer">
        Aggregates public social discussion and market data for personal research only.
        Not financial advice.
      </p>
    </div>
  );
}
