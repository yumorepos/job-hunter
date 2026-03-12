# Job Hunter

Job Hunter is a Python CLI that collects job posts from several public sources, normalizes them, stores them in SQLite, and provides search, digest, recommendation, and export commands.

## What is implemented

- Multi-source collection (`indeed`, `remoteok`, `arbeitnow`, `hackernews`) with retry/backoff and per-source failure isolation.
- Normalized `JobRecord` model with deterministic fingerprinting.
- SQLite persistence with schema migration, deduplication, and optional FTS5 search fallback.
- Deterministic scoring and recommendation reasons (keyword, role/location/remote fit, freshness, duplicate penalty).
- Markdown digest output and CSV/JSON exports.
- CLI commands: `scrape`, `search`, `recommend`, `digest`, `export`, `stats`.

## Requirements

- Python 3.11+

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## CLI usage

```bash
job-hunter scrape
job-hunter search "python backend" --limit 5 --why --days 14 --min-score 5
job-hunter recommend --limit 10 --days 30 --why --remote-only
job-hunter digest --days 7 --output digest.md
job-hunter export --days 7 --csv-path jobs.csv --json-path jobs.json
job-hunter stats
```

## Configuration precedence

Settings are merged in this order:

1. defaults in `Settings`
2. optional `config.toml`
3. environment variables (`JOB_HUNTER_*`)
4. CLI overrides

Example `config.toml`:

```toml
keywords = ["python", "data", "backend"]
exclude = ["staff", "principal"]
locations = ["remote", "canada"]
min_score = 5
```

## Project layout

```text
src/job_hunter/
  cli.py
  config.py
  db.py
  digest.py
  exporters.py
  filters.py
  logging_utils.py
  models.py
  scoring.py
  scrapers/
```

## Development and validation

```bash
ruff check .
black --check --target-version py311 .
pytest -q
mypy src
```

## Current limitations

- Source APIs and HTML fallbacks can change; scraping results may vary over time.
- Tests are offline and do not hit live endpoints.
- Ranking is deterministic and heuristic-based (not ML-based).

## Sample outputs

- Digest: [`example_digest.md`](example_digest.md)
- CSV export: [`example_export.csv`](example_export.csv)
- JSON export: [`example_export.json`](example_export.json)
- Recommendations: [`example_recommend.md`](example_recommend.md)
- Stats report: [`example_stats.md`](example_stats.md)
