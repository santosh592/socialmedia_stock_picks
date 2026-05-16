from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_PATTERN = re.compile(r"\$\{([^}]+)\}")


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve_env(value: Any) -> Any:
    if isinstance(value, str):

        def repl(match: re.Match[str]) -> str:
            return os.environ.get(match.group(1), "")

        return _ENV_PATTERN.sub(repl, value)
    if isinstance(value, dict):
        return {k: _resolve_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_env(v) for v in value]
    return value


class EnvSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://smsp:smsp@127.0.0.1:5432/smsp"
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_username: str = ""
    llm_api_key: str = ""
    market_api_key: str = ""
    app_password: str = ""


class AppConfig(BaseModel):
    name: str = "socialmedia_stock_picks"
    timezone: str = "America/New_York"
    host: str = "127.0.0.1"
    port: int = 8000
    optional_basic_auth: bool = False


class RedditConfig(BaseModel):
    client_id: str = ""
    client_secret: str = ""
    user_agent: str = ""
    subreddits: list[str] = Field(default_factory=list)
    poll_sorts: list[str] = Field(default_factory=lambda: ["new", "hot"])
    max_posts_per_sub_per_poll: int = 100
    comment_fetch: dict[str, Any] = Field(default_factory=dict)


class IngestConfig(BaseModel):
    mode: str = "scheduled"
    interval_minutes: int = 10
    retry: dict[str, int] = Field(default_factory=lambda: {"max_attempts": 5, "backoff_seconds": 30})


class AggregationConfig(BaseModel):
    windows: list[str] = Field(default_factory=lambda: ["4h", "24h", "7d"])
    recompute_on_ingest: bool = True
    min_mentions_for_ticker_listing: int = 3


class TickerExtractionConfig(BaseModel):
    universe: str = "us_equities"
    allowlist_path: str = "data/us_symbols.csv"
    blocklist: list[str] = Field(default_factory=list)
    weights: dict[str, float] = Field(default_factory=dict)


class RankingProfileConfig(BaseModel):
    default_window: str = "24h"
    weights: dict[str, float] = Field(default_factory=dict)
    crowded_penalty: dict[str, float] | None = None


class RankingConfig(BaseModel):
    profiles: dict[str, RankingProfileConfig] = Field(default_factory=dict)


class LLMConfig(BaseModel):
    provider: str = "openai"
    api_key: str = ""
    model: str = "gpt-4o-mini"
    max_input_tokens: int = 12000
    temperature: float = 0.2
    summaries: dict[str, Any] = Field(default_factory=dict)


class Settings(BaseModel):
    app: AppConfig = Field(default_factory=AppConfig)
    reddit: RedditConfig = Field(default_factory=RedditConfig)
    ingest: IngestConfig = Field(default_factory=IngestConfig)
    aggregation: AggregationConfig = Field(default_factory=AggregationConfig)
    ticker_extraction: TickerExtractionConfig = Field(default_factory=TickerExtractionConfig)
    ranking: RankingConfig = Field(default_factory=RankingConfig)
    intents: dict[str, Any] = Field(default_factory=dict)
    market: dict[str, Any] = Field(default_factory=dict)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    opportunities: dict[str, Any] = Field(default_factory=dict)
    digest: dict[str, Any] = Field(default_factory=dict)
    retention: dict[str, Any] = Field(default_factory=dict)

    @property
    def allowlist_path(self) -> Path:
        path = Path(self.ticker_extraction.allowlist_path)
        if not path.is_absolute():
            path = _project_root() / path
        return path


def load_yaml_config(path: Path | None = None) -> dict[str, Any]:
    config_path = path or (_project_root() / "config" / "config.yaml")
    with config_path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return _resolve_env(raw)


@lru_cache
def get_settings() -> Settings:
    env = EnvSettings()
    data = load_yaml_config()
    settings = Settings.model_validate(data)
    # Overlay env secrets when yaml placeholders are empty
    if not settings.reddit.client_id:
        settings.reddit.client_id = env.reddit_client_id
    if not settings.reddit.client_secret:
        settings.reddit.client_secret = env.reddit_client_secret
    if not settings.llm.api_key:
        settings.llm.api_key = env.llm_api_key
    if settings.market.get("api_key") in ("", None):
        settings.market["api_key"] = env.market_api_key
    if "${REDDIT_USERNAME}" in settings.reddit.user_agent or not settings.reddit.user_agent:
        settings.reddit.user_agent = (
            f"socialmedia_stock_picks/0.1 by {env.reddit_username or 'local'}"
        )
    return settings


def get_env() -> EnvSettings:
    return EnvSettings()
