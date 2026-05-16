from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    db: str
    last_ingest: datetime | None = None


class LastIngestInfo(BaseModel):
    id: UUID | None = None
    finished_at: datetime | None = None
    status: str | None = None


class TickerRow(BaseModel):
    rank: int
    ticker: str
    mention_count: int
    weighted_mentions: float
    unique_authors: int
    velocity_pct: float
    price_5d_pct: float | None = None
    summary_tone: str | None = None
    has_summary: bool = False


class OpportunityCard(BaseModel):
    type: str
    ticker: str
    hypothesis: str
    confidence: str
    score: float


class DashboardResponse(BaseModel):
    window: str
    window_end: datetime | None
    profile: str
    last_ingest: LastIngestInfo
    tickers: list[TickerRow] = Field(default_factory=list)
    opportunities: list[OpportunityCard] = Field(default_factory=list)


class IngestRunResponse(BaseModel):
    ingest_run_id: UUID
    status: str


class SettingsResponse(BaseModel):
    config: dict[str, Any]


class SettingsUpdate(BaseModel):
    ingest: dict[str, Any] | None = None
    reddit: dict[str, Any] | None = None
    aggregation: dict[str, Any] | None = None
    llm: dict[str, Any] | None = None


class DigestResponse(BaseModel):
    path: str | None
    markdown: str
    generated_at: datetime | None
