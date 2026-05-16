import { useCallback, useEffect, useState } from "react";
import { fetchDashboard, runIngest } from "../api/client";
import OpportunityGrid from "../components/OpportunityGrid";
import TickerTable from "../components/TickerTable";
import Toolbar from "../components/Toolbar";
import { usePersistedState } from "../hooks/usePersistedState";
import type { DashboardResponse, Profile } from "../types";
import { formatDate } from "../utils/format";

const DEFAULT_WINDOWS: Record<Profile, string> = { day: "24h", swing: "7d" };

export default function DashboardPage() {
  const [profile, setProfile] = usePersistedState<Profile>("smsp.profile", "day");
  const [window, setWindow] = usePersistedState("smsp.window", DEFAULT_WINDOWS.day);
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [ingesting, setIngesting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchDashboard(window, profile);
      setData(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load dashboard");
    } finally {
      setLoading(false);
    }
  }, [window, profile]);

  useEffect(() => {
    load();
  }, [load]);

  const handleProfileChange = (p: Profile) => {
    setProfile(p);
    setWindow(DEFAULT_WINDOWS[p]);
  };

  const handleIngest = async () => {
    setIngesting(true);
    setError(null);
    try {
      await runIngest();
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ingest failed");
    } finally {
      setIngesting(false);
    }
  };

  const ingestStatus = data?.last_ingest?.status;
  const ingestTime = data?.last_ingest?.finished_at;

  return (
    <>
      <Toolbar
        profile={profile}
        window={window}
        onProfileChange={handleProfileChange}
        onWindowChange={setWindow}
        onRefresh={load}
        onIngest={handleIngest}
        loading={loading}
        ingesting={ingesting}
      />

      <div style={{ marginBottom: "1rem", display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
        <span className={`status-pill ${ingestStatus === "success" ? "ok" : ""}`}>
          Ingest: {ingestStatus ?? "—"}
        </span>
        {ingestTime && <span className="status-pill">Last run {formatDate(ingestTime)}</span>}
        {data?.window_end && (
          <span className="status-pill">Data through {formatDate(data.window_end)}</span>
        )}
      </div>

      {error && <div className="error-banner">{error}</div>}

      {loading && !data ? (
        <p className="loading">Loading dashboard…</p>
      ) : (
        <>
          <OpportunityGrid items={data?.opportunities ?? []} window={window} profile={profile} />
          <TickerTable rows={data?.tickers ?? []} window={window} profile={profile} />
        </>
      )}
    </>
  );
}
