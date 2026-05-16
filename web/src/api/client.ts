import type { DashboardResponse, Profile, SummaryPayload, TickerDetailResponse } from "../types";

const API_BASE = import.meta.env.VITE_API_URL ?? "/api/v1";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(body || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export function fetchDashboard(window: string, profile: Profile) {
  const params = new URLSearchParams({ window, profile });
  return request<DashboardResponse>(`/dashboard?${params}`);
}

export function fetchTicker(ticker: string, window: string, profile: Profile) {
  const params = new URLSearchParams({ window, profile });
  return request<TickerDetailResponse>(`/tickers/${ticker}?${params}`);
}

export function summarizeTicker(ticker: string, window: string, force = false) {
  const params = new URLSearchParams({ window, force: String(force) });
  return request<{ summary: SummaryPayload }>(`/tickers/${ticker}/summarize?${params}`, {
    method: "POST",
  });
}

export function runIngest() {
  return request<{ ingest_run_id: string; status: string }>("/ingest/run", {
    method: "POST",
  });
}

export function fetchHealth() {
  return request<{ status: string; db: string; last_ingest: string | null }>("/health");
}
