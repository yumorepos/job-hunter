# Job Hunter (Production Refactor)

Job Hunter is a production-grade CLI for multi-source job discovery, normalization, scoring, storage, and export.

## Highlights

- Modular architecture under `src/job_hunter`.
- Source adapters for Indeed, RemoteOK, Arbeitnow, and HackerNews.
- Normalized job model with deterministic fingerprint deduplication.
- Weighted scoring with human-readable match reasons.
- SQLite with migrations, indexes, and optional FTS5 search.
- Markdown digest plus CSV and JSON export.
- Per-source failure isolation with retries/backoff and degraded-mode operation.
- Packaging, lint/test config, and unit tests.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## CLI

```bash
job-hunter scrape
job-hunter digest --days 7 --output digest.md
job-hunter search "python remote"
job-hunter export --days 7 --csv-path jobs.csv --json-path jobs.json
```

## Configuration

Environment variables:

- `JOB_HUNTER_DB` (default `jobs.db`)
- `JOB_HUNTER_TIMEOUT`
- `JOB_HUNTER_MAX_RETRIES`
- `JOB_HUNTER_BACKOFF`
- `JOB_HUNTER_MIN_SCORE`
- `JOB_HUNTER_SENIORITY`

## Development

```bash
pip install -e .[dev]
ruff check .
black --check .
pytest
```

## Migration Notes / Breaking Changes

- Legacy single-file prototype was replaced with an installable package CLI (`job_hunter.cli`).
- SQLite schema changed to normalized fields (`date_posted`, `remote_flag`, `fingerprint`).
- Deduplication is now fingerprint-based instead of URL-only.
- Digest is relevance-grouped and can include match explanations.
