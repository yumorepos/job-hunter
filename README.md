# 🔍 Job Hunter

**Automated job scraper for Python, data, and automation roles.**

A CLI tool that scrapes public job boards, filters listings by keywords, deduplicates with SQLite, and generates daily markdown digests. Built to automate the most tedious part of job hunting.

## Features

| | Feature | Description |
|-|---------|-------------|
| 🌐 | **Multi-Source Scraping** | Indeed RSS, RemoteOK API, Arbeitnow API, HackerNews Who's Hiring |
| 🔍 | **Smart Filtering** | Keyword matching for Python, data analyst, automation, junior dev roles |
| 🗄️ | **SQLite Deduplication** | Tracks seen listings by URL — no duplicates across runs |
| 📋 | **Markdown Digests** | Generates formatted daily summaries of new listings |
| 🖥️ | **Rich CLI** | Beautiful terminal output with tables and formatting |
| ⚡ | **Async Scraping** | Concurrent HTTP requests for fast data collection |

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Scrape all sources
python job_hunter.py scrape

# Generate today's digest
python job_hunter.py digest

# Search stored listings
python job_hunter.py search "data engineer"
```

## Tech Stack

- **Python 3.12** — async/await, type hints, dataclasses
- **httpx** — async HTTP client for API calls
- **SQLite** — local storage with deduplication
- **Click** — CLI framework
- **Rich** — terminal formatting and tables

## Architecture

```
job_hunter.py
├── Database layer (SQLite init, insert, query, dedup)
├── Scrapers (Indeed RSS, RemoteOK, Arbeitnow, HN)
│   └── Each returns standardized Job objects
├── Filter engine (keyword matching, location)
├── Digest generator (Markdown output)
└── CLI (Click commands: scrape, digest, search)
```

## Why I Built This

Job hunting involves checking the same 5 sites every day. I automated it — because that's what I do. This project demonstrates web scraping, API integration, async Python, data persistence, and CLI design.

## License

MIT
