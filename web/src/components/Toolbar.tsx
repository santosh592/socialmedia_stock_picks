import type { Profile } from "../types";

const WINDOWS = ["4h", "24h", "3d", "7d", "14d", "30d"];

interface ToolbarProps {
  profile: Profile;
  window: string;
  onProfileChange: (p: Profile) => void;
  onWindowChange: (w: string) => void;
  onRefresh: () => void;
  onIngest: () => void;
  loading?: boolean;
  ingesting?: boolean;
}

export default function Toolbar({
  profile,
  window: timeWindow,
  onProfileChange,
  onWindowChange,
  onRefresh,
  onIngest,
  loading,
  ingesting,
}: ToolbarProps) {
  return (
    <div className="toolbar">
      <div className="profile-toggle">
        <button
          type="button"
          className={profile === "day" ? "active" : ""}
          onClick={() => onProfileChange("day")}
        >
          Day
        </button>
        <button
          type="button"
          className={profile === "swing" ? "active" : ""}
          onClick={() => onProfileChange("swing")}
        >
          Swing
        </button>
      </div>
      <select value={timeWindow} onChange={(e) => onWindowChange(e.target.value)} aria-label="Time window">
        {WINDOWS.map((w) => (
          <option key={w} value={w}>
            {w}
          </option>
        ))}
      </select>
      <button type="button" onClick={onRefresh} disabled={loading}>
        {loading ? "Loading…" : "Refresh"}
      </button>
      <button type="button" className="primary" onClick={onIngest} disabled={ingesting}>
        {ingesting ? "Ingesting…" : "Run ingest"}
      </button>
    </div>
  );
}
