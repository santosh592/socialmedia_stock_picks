export type Profile = "day" | "swing";

export interface TickerRow {
  rank: number;
  ticker: string;
  mention_count: number;
  weighted_mentions: number;
  unique_authors: number;
  velocity_pct: number;
  price_5d_pct: number | null;
  summary_tone: string | null;
  has_summary: boolean;
}

export interface OpportunityCard {
  type: string;
  ticker: string;
  hypothesis: string;
  confidence: string;
  score: number;
}

export interface DashboardResponse {
  window: string;
  window_end: string | null;
  profile: Profile;
  last_ingest: {
    id: string | null;
    finished_at: string | null;
    status: string | null;
  };
  tickers: TickerRow[];
  opportunities: OpportunityCard[];
}

export interface SummaryPoint {
  text: string;
  citations?: string[];
}

export interface SummaryPayload {
  $schema?: string;
  ticker: string;
  window: string;
  as_of: string;
  status: "ok" | "insufficient_discussion" | "error";
  tone: string | null;
  bull_points: SummaryPoint[] | string[];
  bear_points: SummaryPoint[] | string[];
  catalysts: SummaryPoint[] | string[];
  risks: SummaryPoint[] | string[];
  consensus: string;
  controversy: string | null;
  citations: { id: string; type?: string; subreddit?: string; quote?: string }[];
  disclaimer: string;
}

export interface TickerDetailResponse {
  ticker: string;
  window: string;
  profile: Profile;
  rollup: {
    mention_count: number;
    weighted_mentions: number;
    unique_authors: number;
    velocity_pct: number;
    rank_score: number;
    intent_counts: Record<string, number> | null;
  };
  market_bars: { date: string; close: number; volume: number }[];
  top_posts: {
    id: string;
    subreddit: string;
    title: string;
    score: number;
    permalink: string;
  }[];
  summary: SummaryPayload | null;
  opportunities: {
    type: string;
    hypothesis: string;
    confidence: string;
    score: number;
    inputs: Record<string, unknown>;
  }[];
}
