import type { SummaryPayload } from "../types";
import { pointText } from "../utils/format";

interface SummaryPanelProps {
  summary: SummaryPayload | null;
  onGenerate?: () => void;
  generating?: boolean;
}

function BulletList({ title, items }: { title: string; items: SummaryPayload["bull_points"] }) {
  if (!items?.length) return null;
  return (
    <div className="summary-block">
      <h3>{title}</h3>
      <ul>
        {items.map((item, i) => (
          <li key={i}>{pointText(item)}</li>
        ))}
      </ul>
    </div>
  );
}

export default function SummaryPanel({ summary, onGenerate, generating }: SummaryPanelProps) {
  if (!summary) {
    return (
      <div className="card">
        <h2 className="section-title">AI summary</h2>
        <p className="empty" style={{ padding: "1rem 0" }}>
          No summary yet.
        </p>
        {onGenerate && (
          <button type="button" className="primary" onClick={onGenerate} disabled={generating}>
            {generating ? "Generating…" : "Generate summary"}
          </button>
        )}
      </div>
    );
  }

  const isOk = summary.status === "ok";

  return (
    <div className="card span-full">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2 className="section-title" style={{ margin: 0 }}>
          AI summary {summary.tone ? `· ${summary.tone}` : ""}
        </h2>
        {onGenerate && (
          <button type="button" onClick={onGenerate} disabled={generating}>
            {generating ? "Regenerating…" : "Regenerate"}
          </button>
        )}
      </div>
      {!isOk ? (
        <p className="consensus" style={{ marginTop: "0.75rem" }}>
          {summary.consensus}
        </p>
      ) : (
        <>
          <p className="consensus" style={{ marginTop: "0.75rem" }}>
            {summary.consensus}
          </p>
          {summary.controversy && (
            <p className="consensus" style={{ color: "var(--text-muted)" }}>
              <strong>Controversy:</strong> {summary.controversy}
            </p>
          )}
          <BulletList title="Bull case" items={summary.bull_points} />
          <BulletList title="Bear case" items={summary.bear_points} />
          <BulletList title="Catalysts" items={summary.catalysts} />
          <BulletList title="Risks" items={summary.risks} />
          {summary.citations?.length > 0 && (
            <div className="summary-block">
              <h3>Sources</h3>
              <ul>
                {summary.citations.map((c) => (
                  <li key={c.id}>
                    <code>{c.id}</code>
                    {c.quote && ` — "${c.quote.slice(0, 120)}…"`}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
      <p className="disclaimer" style={{ marginTop: "1rem", border: "none", padding: 0 }}>
        {summary.disclaimer}
      </p>
    </div>
  );
}
