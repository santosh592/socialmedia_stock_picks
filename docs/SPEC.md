# Social Media Stock Picks — Technical Specification

**Version:** 0.1  
**Status:** Draft  
**Last updated:** 2026-05-16  
**Companion:** [DESIGN.md](./DESIGN.md)

---

## 1. Scope

This document specifies implementable requirements for v0.1 of the personal US-equities Reddit research tool: data models, APIs, configuration, algorithms, LLM contracts, and acceptance criteria.

---

## 2. System context

```
┌─────────────┐     HTTPS      ┌──────────────┐
│  Web UI     │ ◄────────────► │  FastAPI     │
└─────────────┘                │  + Workers   │
                               └──────┬───────┘
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                 ▼
              PostgreSQL         Reddit API        Market + LLM APIs
```

**Runtime components:**

| Component | Responsibility |
|-----------|----------------|
| `api` | REST endpoints, auth gate, read models |
| `worker-ingest` | Poll Reddit, upsert posts/comments, extract mentions |
| `worker-rollup` | Compute `ticker_rollups`, opportunity signals |
| `worker-summary` | LLM calls, cache summaries |
| `worker-digest` | Render markdown digest |

---

## 3. Configuration

### 3.1 File location

`config/config.yaml` with secrets in `.env` (see `.env.example`).

### 3.2 Schema

```yaml
# config/config.yaml

app:
  name: socialmedia_stock_picks
  timezone: America/New_York
  host: 127.0.0.1
  port: 8000
  optional_basic_auth: false  # if true, require APP_PASSWORD

reddit:
  client_id: ${REDDIT_CLIENT_ID}
  client_secret: ${REDDIT_CLIENT_SECRET}
  user_agent: socialmedia_stock_picks/0.1 by ${REDDIT_USERNAME}
  subreddits:
    - wallstreetbets
    - Daytrading
    - stocks
    - StockMarket
    - options
  poll_sorts: [new, hot]
  max_posts_per_sub_per_poll: 100
  comment_fetch:
    enabled: true
    max_depth: 2
    min_post_score: 5
    max_comments_per_post: 200

ingest:
  mode: scheduled              # scheduled | manual_only
  interval_minutes: 10
  retry:
    max_attempts: 5
    backoff_seconds: 30

aggregation:
  windows: [1h, 4h, 24h, 3d, 7d]
  recompute_on_ingest: true
  min_mentions_for_ticker_listing: 3

ticker_extraction:
  universe: us_equities
  allowlist_path: data/us_symbols.csv
  blocklist: [AI, ON, IT, ALL, FOR, DD, USA, CEO, ETF, IPO, SEC, FDA, EPS, PE, PS, YOLO]
  weights:
    title: 2.0
    post_body: 1.5
    comment: 1.0
    dd_flair: 1.3
    negative_score_multiplier: 0.5

ranking:
  profiles:
    day:
      default_window: 24h
      weights:
        unique_authors: 0.35
        velocity: 0.40
        weighted_mentions: 0.15
        engagement_depth: 0.10
      crowded_penalty:
        price_5d_pct_above: 8.0
        penalty_factor: 0.7
    swing:
      default_window: 7d
      weights:
        unique_authors: 0.30
        velocity: 0.20
        weighted_mentions: 0.20
        subreddit_breadth: 0.20
        engagement_depth: 0.10

intents:
  classifier: keyword  # keyword | llm (future)
  keywords:
    yolo: [yolo, calls, puts, 0dte, lambo]
    dd: [dd, due diligence, thesis]
    earnings: [earnings, er, guidance, beat, miss]
    technical: [support, resistance, breakout, rsi, macd]
    news: [sec filing, 8-k, pr newswire, bloomberg]
    options: [iv, implied volatility, gamma, delta]
    short_squeeze: [short squeeze, si%, borrow rate, ctB]

market:
  provider: tiingo  # tiingo | polygon | alpaca
  api_key: ${MARKET_API_KEY}
  daily_bars_lookback_days: 60
  sync_on_rollup: true

llm:
  provider: openai  # openai | anthropic
  api_key: ${LLM_API_KEY}
  model: gpt-4o-mini
  max_input_tokens: 12000
  temperature: 0.2
  summaries:
    mode: both  # on_demand | scheduled | both
    scheduled_top_n: 15
    schedule_cron: "0 7,12,16 * * 1-5"
    cache_ttl_minutes: 120
    min_weighted_mentions: 5
    top_posts: 15
    top_comments: 30

opportunities:
  enabled_types: [O1, O2, O3, O4, O5, O6]
  O1:
    velocity_z_min: 2.0
    price_5d_abs_max_pct: 3.0
  O2:
    velocity_min_pct: 50
    price_5d_min_pct: 8.0
  O3:
    bullish_intent_drop_pp: 15
    windows: [7d]
  O4:
    window: 4h
    velocity_min_pct: 100
    volume_vs_20d_min: 1.5
  O5:
    dd_post_min: 2
    price_5d_abs_max_pct: 4.0
    min_comments: 20
  O6:
    options_sub_mention_share_min: 0.25

digest:
  enabled: true
  output_path: data/digests
  schedule_cron: "30 7 * * 1-5"
  window: 24h
  profile: day
  top_n_tickers: 20

retention:
  raw_posts_days: 90
  raw_comments_days: 90
  rollups_days: 365
```

### 3.3 Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | `postgresql+asyncpg://...` |
| `REDDIT_CLIENT_ID` | Yes | Reddit app client ID |
| `REDDIT_CLIENT_SECRET` | Yes | Reddit app secret |
| `REDDIT_USERNAME` | Yes | For user-agent string |
| `LLM_API_KEY` | Yes | LLM provider key |
| `MARKET_API_KEY` | Yes | Market data provider key |
| `APP_PASSWORD` | If basic auth | Single-user password |

---

## 4. Data model

### 4.1 Entity relationship

```
subreddits 1──* reddit_posts 1──* reddit_comments
reddit_posts *──* ticker_mentions
reddit_comments *──* ticker_mentions
ticker_mentions ──► ticker_rollups (aggregated)
ticker_rollups ──► summaries (optional)
ticker_rollups ──► opportunity_signals
```

### 4.2 Table definitions

#### `subreddits`

| Column | Type | Notes |
|--------|------|-------|
| `name` | `VARCHAR(64)` PK | e.g. `stocks` |
| `enabled` | `BOOLEAN` | |
| `poll_sorts` | `JSONB` | override global |
| `created_at` | `TIMESTAMPTZ` | |

#### `ingest_runs`

| Column | Type | Notes |
|--------|------|-------|
| `id` | `UUID` PK | |
| `started_at` | `TIMESTAMPTZ` | |
| `finished_at` | `TIMESTAMPTZ` | nullable |
| `status` | `VARCHAR(16)` | `running`, `success`, `failed` |
| `posts_fetched` | `INTEGER` | |
| `comments_fetched` | `INTEGER` | |
| `mentions_created` | `INTEGER` | |
| `errors` | `JSONB` | per-sub errors |

#### `reddit_posts`

| Column | Type | Notes |
|--------|------|-------|
| `id` | `VARCHAR(16)` PK | Reddit thing ID e.g. `t3_abc` |
| `subreddit` | `VARCHAR(64)` FK | |
| `author` | `VARCHAR(64)` | |
| `created_utc` | `TIMESTAMPTZ` | |
| `title` | `TEXT` | |
| `body` | `TEXT` | nullable |
| `url` | `TEXT` | |
| `score` | `INTEGER` | |
| `num_comments` | `INTEGER` | |
| `flair` | `VARCHAR(128)` | nullable |
| `permalink` | `TEXT` | |
| `ingested_at` | `TIMESTAMPTZ` | |
| `updated_at` | `TIMESTAMPTZ` | |

Indexes: `(subreddit, created_utc DESC)`, `(created_utc DESC)`.

#### `reddit_comments`

| Column | Type | Notes |
|--------|------|-------|
| `id` | `VARCHAR(16)` PK | `t1_abc` |
| `post_id` | `VARCHAR(16)` FK | |
| `parent_id` | `VARCHAR(16)` | |
| `author` | `VARCHAR(64)` | |
| `created_utc` | `TIMESTAMPTZ` | |
| `body` | `TEXT` | |
| `score` | `INTEGER` | |
| `permalink` | `TEXT` | |
| `ingested_at` | `TIMESTAMPTZ` | |

Index: `(post_id, created_utc)`.

#### `post_intents`

| Column | Type | Notes |
|--------|------|-------|
| `post_id` | `VARCHAR(16)` PK FK | |
| `intent` | `VARCHAR(32)` | |
| `confidence` | `REAL` | 0–1 |
| `classified_at` | `TIMESTAMPTZ` | |

#### `ticker_mentions`

| Column | Type | Notes |
|--------|------|-------|
| `id` | `BIGSERIAL` PK | |
| `ticker` | `VARCHAR(16)` | normalized uppercase |
| `source_type` | `VARCHAR(8)` | `post`, `comment` |
| `source_id` | `VARCHAR(16)` | |
| `subreddit` | `VARCHAR(64)` | denormalized |
| `weight` | `REAL` | after extraction weights |
| `location` | `VARCHAR(16)` | `title`, `body` |
| `created_utc` | `TIMESTAMPTZ` | from source |
| `ingested_at` | `TIMESTAMPTZ` | |

Unique: `(ticker, source_type, source_id)` — one row per ticker per source.

Indexes: `(ticker, created_utc DESC)`, `(created_utc DESC)`.

#### `ticker_rollups`

| Column | Type | Notes |
|--------|------|-------|
| `id` | `BIGSERIAL` PK | |
| `ticker` | `VARCHAR(16)` | |
| `window` | `VARCHAR(8)` | `4h`, `24h`, `7d`, etc. |
| `window_end` | `TIMESTAMPTZ` | exclusive end anchor |
| `mention_count` | `INTEGER` | |
| `weighted_mentions` | `REAL` | |
| `unique_authors` | `INTEGER` | |
| `velocity_pct` | `REAL` | vs prior window |
| `engagement_depth` | `REAL` | avg comments |
| `subreddit_breadth` | `INTEGER` | |
| `intent_counts` | `JSONB` | |
| `rank_score` | `REAL` | profile-specific |
| `profile` | `VARCHAR(8)` | `day`, `swing` |
| `computed_at` | `TIMESTAMPTZ` | |

Unique: `(ticker, window, window_end, profile)`.

Index: `(window, window_end, profile, rank_score DESC)`.

#### `market_bars`

| Column | Type | Notes |
|--------|------|-------|
| `ticker` | `VARCHAR(16)` | |
| `date` | `DATE` | |
| `open` | `NUMERIC` | |
| `high` | `NUMERIC` | |
| `low` | `NUMERIC` | |
| `close` | `NUMERIC` | |
| `volume` | `BIGINT` | |

PK: `(ticker, date)`.

#### `summaries`

| Column | Type | Notes |
|--------|------|-------|
| `id` | `UUID` PK | |
| `ticker` | `VARCHAR(16)` | |
| `window` | `VARCHAR(8)` | |
| `window_end` | `TIMESTAMPTZ` | |
| `payload` | `JSONB` | see §6 |
| `model` | `VARCHAR(64)` | |
| `prompt_version` | `VARCHAR(16)` | |
| `cache_key` | `VARCHAR(128)` UNIQUE | |
| `created_at` | `TIMESTAMPTZ` | |

#### `opportunity_signals`

| Column | Type | Notes |
|--------|------|-------|
| `id` | `UUID` PK | |
| `ticker` | `VARCHAR(16)` | |
| `type` | `VARCHAR(4)` | O1–O6 |
| `window` | `VARCHAR(8)` | |
| `window_end` | `TIMESTAMPTZ` | |
| `profile` | `VARCHAR(8)` | |
| `score` | `REAL` | |
| `confidence` | `VARCHAR(8)` | `low`, `medium` |
| `hypothesis` | `TEXT` | |
| `inputs` | `JSONB` | metrics used |
| `created_at` | `TIMESTAMPTZ` | |

Index: `(window_end, profile, type, score DESC)`.

#### `app_config`

| Column | Type | Notes |
|--------|------|-------|
| `key` | `VARCHAR(128)` PK | |
| `value` | `JSONB` | |
| `updated_at` | `TIMESTAMPTZ` | |

Settings API may mirror `config.yaml` into this table for runtime edits.

---

## 5. Algorithms

### 5.1 Ticker extraction

```text
INPUT:  text, location (title|body), source metadata
OUTPUT: list of valid tickers with base weight

1. Find patterns: \$[A-Z]{1,5}\b, \b[A-Z]{1,5}\b (word boundaries)
2. Uppercase normalization; map BRK-B → BRK.B
3. Drop if in blocklist
4. Keep if in allowlist (us_symbols.csv)
5. weight = config.ticker_extraction.weights[location]
           * (dd_flair ? dd_flair_mult : 1)
           * (score < 0 ? negative_mult : 1)
6. Insert ticker_mentions (idempotent)
```

### 5.2 Rollup computation

For each `(ticker, window, window_end)`:

```text
mention_count      = COUNT(ticker_mentions in window)
weighted_mentions  = SUM(weight)
unique_authors     = COUNT(DISTINCT author from joined sources)
velocity_pct       = (weighted_now - weighted_prev) / max(weighted_prev, 1) * 100
engagement_depth   = AVG(post.num_comments) for posts with mentions
subreddit_breadth  = COUNT(DISTINCT subreddit)
intent_counts      = histogram from post_intents for mentioning posts
```

### 5.3 Rank score

For profile `p` with weights `w`:

```text
rank_score =
    w.unique_authors    * norm(unique_authors) +
    w.velocity          * norm(velocity_pct) +
    w.weighted_mentions * norm(weighted_mentions) +
    w.engagement_depth  * norm(engagement_depth) +
    w.subreddit_breadth * norm(subreddit_breadth)   # swing only

# norm(x) = min-max across all tickers in same window_end, profile

# Day profile crowded penalty (if price_5d_pct > threshold):
rank_score *= crowded_penalty_factor
```

### 5.4 Opportunity evaluation

Run after rollups and `market_bars` sync. Emit signal if rule predicates true. `confidence`:

- `medium` if primary metric &gt; 2.5σ or rule margin &gt; 20% above threshold
- else `low`

See `config.opportunities.*` for thresholds (§3.2).

### 5.5 Content version (summary cache invalidation)

```text
content_version = SHA256(
  concat(sorted mention source_ids in window) ||
  window_end.isoformat()
)
cache_key = f"{ticker}:{window}:{content_version}"
```

---

## 6. LLM contract

### 6.1 Request structure

```json
{
  "ticker": "NVDA",
  "window": "7d",
  "window_end": "2026-05-16T16:00:00Z",
  "stats": {
    "weighted_mentions": 412.5,
    "unique_authors": 198,
    "velocity_pct": 84.2,
    "intent_counts": {"dd": 12, "yolo": 45, "earnings": 8}
  },
  "market_snippet": {
    "price_5d_pct": 2.1,
    "volume_vs_20d": 1.1
  },
  "posts": [
    {
      "id": "t3_xxx",
      "subreddit": "stocks",
      "title": "...",
      "body": "...",
      "score": 120,
      "permalink": "https://reddit.com/..."
    }
  ],
  "comments": [
    {
      "id": "t1_yyy",
      "post_id": "t3_xxx",
      "body": "...",
      "score": 45,
      "permalink": "..."
    }
  ]
}
```

### 6.2 Response schema (strict JSON)

```json
{
  "$schema": "summary_v1",
  "ticker": "NVDA",
  "window": "7d",
  "as_of": "2026-05-16T16:00:00Z",
  "status": "ok",
  "tone": "mixed",
  "bull_points": [
    {"text": "...", "citations": ["t3_xxx"]}
  ],
  "bear_points": [
    {"text": "...", "citations": ["t1_yyy"]}
  ],
  "catalysts": [
    {"text": "...", "citations": ["t3_aaa"]}
  ],
  "risks": [
    {"text": "...", "citations": ["t3_bbb"]}
  ],
  "consensus": "One paragraph.",
  "controversy": "One paragraph or null.",
  "citations": [
    {
      "id": "t3_xxx",
      "type": "post",
      "subreddit": "stocks",
      "quote": "Short verbatim excerpt <= 200 chars"
    }
  ],
  "disclaimer": "AI-generated summary of public posts; not financial advice."
}
```

`status` enum: `ok` | `insufficient_discussion` | `error`

When `insufficient_discussion`, arrays empty and `consensus` explains threshold not met.

### 6.3 System prompt requirements

1. Use only provided `posts` and `comments`.
2. Attach at least one citation ID to every bullet in bull/bear/catalysts/risks.
3. Do not predict price targets or recommend trades.
4. Output valid JSON matching schema; no markdown wrapper.

`prompt_version` in DB: `summary_v1`.

---

## 7. REST API

Base URL: `http://127.0.0.1:8000/api/v1`

### 7.1 Conventions

- Timestamps: ISO 8601 UTC
- Tickers: uppercase US symbols
- Errors: `{ "detail": "...", "code": "..." }`
- Pagination: `?limit=50&offset=0`

### 7.2 Endpoints

#### `GET /health`

```json
{ "status": "ok", "db": "ok", "last_ingest": "2026-05-16T15:50:00Z" }
```

#### `GET /dashboard`

| Query | Type | Default |
|-------|------|---------|
| `window` | string | profile default |
| `profile` | `day` \| `swing` | `day` |
| `sort` | see DESIGN §4.3 | `rank_score` |
| `limit` | int | 50 |

**Response 200:**

```json
{
  "window": "24h",
  "window_end": "2026-05-16T16:00:00Z",
  "profile": "day",
  "last_ingest": { "id": "uuid", "finished_at": "...", "status": "success" },
  "tickers": [
    {
      "rank": 1,
      "ticker": "NVDA",
      "mention_count": 380,
      "weighted_mentions": 412.5,
      "unique_authors": 198,
      "velocity_pct": 84.2,
      "price_5d_pct": 2.1,
      "summary_tone": "mixed",
      "has_summary": true
    }
  ],
  "opportunities": [
    {
      "type": "O1",
      "ticker": "AMD",
      "hypothesis": "Mention velocity elevated while 5d price change is flat.",
      "confidence": "medium",
      "score": 0.82
    }
  ]
}
```

#### `GET /tickers/{ticker}`

| Query | Type | Default |
|-------|------|---------|
| `window` | string | `7d` |

**Response 200:**

```json
{
  "ticker": "NVDA",
  "window": "7d",
  "rollup": { },
  "mention_timeline": [
    {"bucket_start": "...", "weighted_mentions": 12.0}
  ],
  "market_bars": [
    {"date": "2026-05-12", "close": 120.5, "volume": 45000000}
  ],
  "top_posts": [ ],
  "summary": { },
  "opportunities": [ ]
}
```

#### `POST /tickers/{ticker}/summarize`

| Query | Type | Default |
|-------|------|---------|
| `window` | string | required |
| `force` | bool | false |

Triggers LLM if cache miss or `force=true`. Returns same `summary` object as GET.

**Response 202** if queued (async worker); **200** if synchronous.

#### `GET /opportunities`

| Query | Type |
|-------|------|
| `window` | string |
| `profile` | day \| swing |
| `type` | O1–O6 optional filter |

#### `GET /settings`

Returns effective config (secrets redacted).

#### `PUT /settings`

Partial update; persists to `app_config` and optionally reloads workers.

```json
{
  "ingest": { "interval_minutes": 15 },
  "reddit": { "subreddits": ["stocks", "wallstreetbets"] }
}
```

#### `POST /ingest/run`

Body optional: `{ "subreddits": ["stocks"] }`

**Response 202:**

```json
{ "ingest_run_id": "uuid", "status": "running" }
```

#### `GET /ingest/runs/{id}`

Poll ingest status.

#### `GET /digest/latest`

Returns `{ "path": "...", "markdown": "...", "generated_at": "..." }`.

---

## 8. Background jobs

| Job | Trigger | Action |
|-----|---------|--------|
| `ingest` | cron: `interval_minutes` | Reddit poll → mentions |
| `rollup` | after ingest | Recompute rollups + opportunities |
| `market_sync` | after rollup | Fetch missing daily bars for active tickers |
| `summary_scheduled` | cron: `llm.summaries.schedule_cron` | Top N summaries |
| `digest` | cron: `digest.schedule_cron` | Write markdown file |

Job locking: advisory lock or `job_locks` table to prevent overlapping ingest.

---

## 9. UI requirements (MVP)

| ID | Requirement |
|----|-------------|
| UI-1 | Dashboard loads in &lt; 2s with 50 tickers (cached rollups) |
| UI-2 | Profile and window selectors persist in localStorage |
| UI-3 | Ticker page shows summary with clickable citation links to Reddit |
| UI-4 | Settings page maps to `PUT /settings` |
| UI-5 | Global disclaimer visible on dashboard and ticker pages |
| UI-6 | Manual ingest button with status indicator |

---

## 10. Acceptance criteria (v0.1)

### 10.1 Ingestion

- [ ] **AC-I1:** Scheduled ingest runs at configured interval when `mode=scheduled`
- [ ] **AC-I2:** Manual `POST /ingest/run` completes and populates `ingest_runs`
- [ ] **AC-I3:** Duplicate posts do not duplicate mentions (idempotent upsert)
- [ ] **AC-I4:** Blocklisted tokens are not stored as tickers

### 10.2 Aggregation

- [ ] **AC-A1:** Rollups exist for all configured windows after ingest
- [ ] **AC-A2:** `velocity_pct` matches manual calculation on test fixture
- [ ] **AC-A3:** Day and swing profiles produce different `rank_score` orderings on same fixture

### 10.3 Summaries

- [ ] **AC-S1:** Summary JSON validates against §6.2 schema
- [ ] **AC-S2:** Every bull/bear bullet includes ≥1 citation ID present in input
- [ ] **AC-S3:** Cache hit on second request within TTL unless content changes
- [ ] **AC-S4:** `insufficient_discussion` when mentions &lt; `min_weighted_mentions`

### 10.4 Opportunities

- [ ] **AC-O1:** Each enabled type generates ≥1 signal on synthetic test data
- [ ] **AC-O2:** Cards include hypothesis, confidence, and input metrics
- [ ] **AC-O3:** No card text contains "buy", "sell", or "recommend"

### 10.5 API / ops

- [ ] **AC-P1:** All §7 endpoints return documented shapes
- [ ] **AC-P2:** Secrets never appear in `GET /settings` response
- [ ] **AC-P3:** Digest file written to `digest.output_path` on schedule

---

## 11. Test fixtures

Provide under `tests/fixtures/`:

| Fixture | Purpose |
|---------|---------|
| `sample_posts.json` | 20 posts with overlapping tickers |
| `sample_comments.json` | Comments for velocity tests |
| `us_symbols_sample.csv` | 100 symbols for allowlist |
| `expected_rollups_24h.json` | Golden rollup output |
| `llm_summary_ok.json` | Valid summary response |

---

## 12. Repository layout (target)

```text
socialmedia_stock_picks/
├── config/
│   └── config.yaml
├── data/
│   └── us_symbols.csv
├── docs/
│   ├── DESIGN.md
│   └── SPEC.md
├── src/
│   ├── api/
│   ├── workers/
│   ├── services/
│   │   ├── reddit/
│   │   ├── ticker/
│   │   ├── rollup/
│   │   ├── summary/
│   │   └── opportunities/
│   └── models/
├── tests/
├── alembic/
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## 13. Version history

| Version | Date | Changes |
|---------|------|---------|
| 0.1 | 2026-05-16 | Initial design decisions: day/swing, US only, configurable, LLM, personal, no broker |
