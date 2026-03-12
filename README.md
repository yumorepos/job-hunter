# Job Hunter CLI

Job Hunter is an intelligent, lightweight job discovery engine that scrapes multiple sources, normalizes records, ranks opportunities, and exports portfolio-friendly outputs.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Quickstart

```bash
job-hunter scrape
job-hunter search "python backend" --why --days 14
job-hunter digest --days 7 --output digest.md
job-hunter export --days 7 --csv-path jobs.csv --json-path jobs.json
job-hunter stats
```

## Configuration

Supports layered config resolution:

`defaults → config.toml → environment variables → CLI overrides`

Example `config.toml`:

```toml
keywords = ["python", "data", "backend"]
exclude = ["senior", "staff"]
locations = ["remote", "canada"]
min_score = 50
```

## Example Output

- Digest example: [`example_digest.md`](example_digest.md)
- CSV export example: [`example_export.csv`](example_export.csv)
- JSON export example: [`example_export.json`](example_export.json)

Search example:

```text
1. [ 34.0] Python Backend Developer | Acme | Remote | https://example.com/jobs/1
   why: title matched: python, backend; remote preference; fresh posting
```

Stats example:

```text
Total jobs collected: 182
New jobs today: 21
Top companies:
- Acme: 9
- DataCorp: 7
```

## Architecture

```text
CLI (click)
  ├── config.py (defaults + TOML + env + overrides)
  ├── scrapers/* (source adapters + retry/fallback)
  ├── models.py (normalization + fingerprint)
  ├── db.py (SQLite schema, FTS, fuzzy search, stats)
  ├── scoring.py (weighted ranking + match reasons + duplicate penalty)
  ├── digest.py / exporters.py (Markdown, CSV, JSON)
  └── tests/* (scoring, DB, config, resilience)
```

## Contributing

```bash
pip install -e .[dev]
ruff check .
black --check .
pytest -q
```

Please include tests for behavior changes and keep modules single-purpose.
