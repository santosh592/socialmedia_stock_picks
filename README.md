# Social Media Stock Picks

Personal research tool that ingests Reddit stock discussion, ranks US tickers by attention, summarizes narratives with LLM (cited), and surfaces watchlist-style opportunity hypotheses.

**Docs:** [Design](docs/DESIGN.md) · [Technical spec](docs/SPEC.md)

## Prerequisites

- Python 3.12+
- Docker (for PostgreSQL)
- Reddit API app credentials ([create app](https://www.reddit.com/prefs/apps))
- LLM API key (OpenAI or compatible)
- Market data API key (e.g. Tiingo) — needed when market sync is implemented

## Quick start

```bash
# 1. Database
docker compose up -d

# 2. Python environment
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 3. Environment
cp .env.example .env
# Edit .env with your credentials

# 4. Migrations
alembic upgrade head

# 5. Run API
smsp-api
# or: uvicorn api.main:app --reload --app-dir src
```

API base: `http://127.0.0.1:8000/api/v1`  
OpenAPI: `http://127.0.0.1:8000/docs`

## Key endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health + last ingest time |
| GET | `/dashboard` | Top tickers + opportunities |
| GET | `/tickers/{symbol}` | Ticker detail |
| POST | `/tickers/{symbol}/summarize` | Generate LLM summary |
| POST | `/ingest/run` | Manual ingest |
| GET | `/settings` | Effective config (secrets redacted) |
| GET | `/digest/latest` | Latest markdown digest |

Query params for dashboard: `window`, `profile` (`day` | `swing`).

## Configuration

- `config/config.yaml` — subreddits, windows, ranking weights, LLM, opportunities
- `.env` — secrets (`DATABASE_URL`, Reddit, LLM, market keys)
- `data/us_symbols.csv` — US ticker allowlist (replace with full symbol list for production)

## Project layout

```
config/          # YAML settings
data/            # symbol allowlist, digests
docs/            # DESIGN.md, SPEC.md
src/
  api/           # FastAPI routes
  core/          # config, database
  models/        # SQLAlchemy entities
  services/      # ticker, rollup, summary, reddit, opportunities
  workers/       # ingest, digest, scheduler
alembic/         # migrations
tests/
```

## Implementation status (v0.1 scaffold)

- [x] Postgres schema + Alembic migration
- [x] FastAPI skeleton + config loading
- [x] Ticker extraction + intent classifier (keyword)
- [x] Rollup / opportunity engines (skeleton logic)
- [ ] Reddit ingest (`services/reddit/`)
- [ ] Market data sync
- [ ] Full LLM summary pipeline with citations
- [ ] Web UI

## Disclaimer

Aggregates public social discussion and market data for **personal research only**. Not financial advice.
