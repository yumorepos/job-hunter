# Job Hunter — Intelligent Job Discovery Engine

A production-grade Python CLI that aggregates multi-source jobs, normalizes them, ranks them with explainable scoring, and delivers actionable recommendations.

## Why this project

Job Hunter is designed as a **job intelligence engine**, not just a scraper:
- resilient source collection with graceful degradation
- explainable ranking and personalized recommendations
- deduplication across near-duplicate postings
- export-ready outputs for portfolio and workflow automation

## Key features

- Multi-source scraping with retry/backoff, rotating User-Agent, proxy support, and per-source failure isolation.
- Layered config precedence: `defaults → config.toml → environment variables → CLI overrides`.
- Weighted ranking with reasons: keyword relevance, role/location/remote alignment, freshness, penalties.
- Near-duplicate handling with fuzzy title/company/description similarity and newest-posting preference.
- Fast SQLite storage with optional FTS5 + fuzzy reranking.
- Human-readable digest + CSV/JSON exports.
- Market intelligence report via `stats` and personalized picks via `recommend`.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

## CLI examples

```bash
job-hunter scrape
job-hunter search "python backend" --limit 5 --why --days 14 --min-score 5
job-hunter recommend --limit 10 --days 30 --why --remote-only
job-hunter digest --days 7 --output digest.md
job-hunter export --days 7 --csv-path jobs.csv --json-path jobs.json
job-hunter stats
```

## Configuration

Create `config.toml` (optional):

```toml
keywords = ["python", "data", "backend"]
exclude = ["senior", "staff"]
locations = ["remote", "canada"]
min_score = 50
```

Supported environment overrides include:
- `JOB_HUNTER_DB`
- `JOB_HUNTER_TIMEOUT`
- `JOB_HUNTER_MAX_RETRIES`
- `JOB_HUNTER_BACKOFF`
- `JOB_HUNTER_PROXY`
- `JOB_HUNTER_KEYWORDS`
- `JOB_HUNTER_EXCLUDE`
- `JOB_HUNTER_LOCATIONS`
- `JOB_HUNTER_MIN_SCORE`

## Example outputs

- Digest: [`example_digest.md`](example_digest.md)
- CSV export: [`example_export.csv`](example_export.csv)
- JSON export: [`example_export.json`](example_export.json)
- Recommendations: [`example_recommend.md`](example_recommend.md)
- Stats report: [`example_stats.md`](example_stats.md)

### Sample recommend output

```text
Recommended Jobs

1. Backend Python Engineer — Stripe
   Score: 91.0
   Location: Remote
   Posted: 2026-03-10
   Why recommended:
   - strong title relevance: python, backend
   - role alignment boost
   - remote preference boost
   - freshness boost
```

### Sample stats output

```text
Total jobs collected: 182
New jobs today: 21
Top companies hiring:
- Stripe: 9
- Shopify: 7
Top job locations:
- Remote: 113
```

## Architecture overview

```text
src/job_hunter/
  cli.py          # command orchestration (search/digest/export/stats/recommend)
  config.py       # defaults + config file + env + CLI override resolution
  db.py           # schema, dedupe-aware insert, FTS/fuzzy search, stats
  scoring.py      # explainable weighted scoring + duplicate penalties
  models.py       # normalized job model + fingerprint/date normalization
  scrapers/*      # source adapters + resilient fetch/fallback behavior
  digest.py       # markdown digest rendering
  exporters.py    # CSV/JSON exports
```

## Reliability and degraded mode

If a source fails (e.g., upstream 403/429), scraping continues for remaining sources. Failures are logged and reported without crashing the run.

## Development

```bash
ruff check .
black --check .
pytest -q
```

## Contributing

PRs should keep modules focused, add tests for behavior changes, and preserve graceful failure behavior for external sources.
