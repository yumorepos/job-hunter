from __future__ import annotations

import asyncio
from pathlib import Path

import click
import httpx

from .config import DEFAULT_SETTINGS, Settings
from .db import connect, fetch_recent_jobs, search_jobs as db_search_jobs, upsert_jobs
from .digest import build_markdown_digest
from .exporters import export_csv, export_json
from .filters import filter_scored_jobs
from .logging_utils import configure_logging
from .models import JobRecord
from .scoring import dedupe_similarity_penalty, score_job
from .scrapers.arbeitnow import ArbeitnowScraper
from .scrapers.base import run_scraper_safe
from .scrapers.hackernews import HackerNewsScraper
from .scrapers.indeed import IndeedScraper
from .scrapers.remoteok import RemoteOKScraper


SCRAPERS = [IndeedScraper(), RemoteOKScraper(), ArbeitnowScraper(), HackerNewsScraper()]


def _rows_to_jobs(rows: list) -> list[JobRecord]:
    return [
        JobRecord(
            title=r["title"],
            company=r["company"],
            location=r["location"],
            source=r["source"],
            url=r["url"],
            date_posted=r["date_posted"],
            remote_flag=bool(r["remote_flag"]),
            tags=(r["tags"] or "").split(",") if r["tags"] else [],
            description=r["description"],
            fingerprint=r["fingerprint"],
        )
        for r in rows
    ]


async def scrape_all(settings: Settings) -> tuple[dict[str, int], dict[str, str]]:
    async with httpx.AsyncClient(
        follow_redirects=True, headers={"User-Agent": "job-hunter/2.0"}
    ) as client:
        results = await asyncio.gather(
            *[run_scraper_safe(scraper, client, settings) for scraper in SCRAPERS]
        )

    conn = connect(settings.db_path)
    stats: dict[str, int] = {}
    failures: dict[str, str] = {}
    for source, jobs, error in results:
        if error:
            failures[source] = error
            stats[source] = 0
            continue
        stats[source] = upsert_jobs(conn, jobs)
    conn.close()
    return stats, failures


@click.group()
@click.option("--verbose", is_flag=True, default=False)
def cli(verbose: bool) -> None:
    """Job Hunter CLI."""
    configure_logging(verbose)


@cli.command()
def scrape() -> None:
    """Scrape all sources and persist normalized jobs."""
    stats, failures = asyncio.run(scrape_all(DEFAULT_SETTINGS))
    total = sum(stats.values())
    click.echo(f"New jobs inserted: {total}")
    for source, count in stats.items():
        click.echo(f"- {source}: {count}")
    if failures:
        click.echo("Warnings (degraded mode):")
        for source, err in failures.items():
            click.echo(f"  * {source}: {err}")


@cli.command()
@click.option("--days", default=7, show_default=True)
@click.option("--output", type=click.Path(path_type=Path), default=Path("digest.md"))
@click.option("--include-reasons/--no-include-reasons", default=True)
def digest(days: int, output: Path, include_reasons: bool) -> None:
    """Generate markdown digest from recent jobs."""
    conn = connect(DEFAULT_SETTINGS.db_path)
    jobs = _rows_to_jobs(fetch_recent_jobs(conn, days=days))
    conn.close()
    scored = dedupe_similarity_penalty([score_job(job, DEFAULT_SETTINGS) for job in jobs])
    filtered = filter_scored_jobs(scored, DEFAULT_SETTINGS)
    output.write_text(
        build_markdown_digest(filtered, include_reasons=include_reasons), encoding="utf-8"
    )
    click.echo(f"Digest written to {output} ({len(filtered)} jobs)")


@cli.command()
@click.argument("query")
@click.option("--limit", default=20, show_default=True)
def search(query: str, limit: int) -> None:
    """Search jobs using FTS or LIKE fallback."""
    conn = connect(DEFAULT_SETTINGS.db_path)
    rows = db_search_jobs(conn, query, limit=limit)
    conn.close()
    if not rows:
        click.echo("No results")
        return
    for idx, row in enumerate(rows, start=1):
        click.echo(f"{idx}. {row['title']} | {row['company']} | {row['source']} | {row['url']}")


@cli.command("export")
@click.option("--days", default=7, show_default=True)
@click.option("--csv-path", type=click.Path(path_type=Path), default=Path("jobs.csv"))
@click.option("--json-path", type=click.Path(path_type=Path), default=Path("jobs.json"))
def export_cmd(days: int, csv_path: Path, json_path: Path) -> None:
    """Export filtered jobs to CSV and JSON."""
    conn = connect(DEFAULT_SETTINGS.db_path)
    jobs = _rows_to_jobs(fetch_recent_jobs(conn, days=days))
    conn.close()
    scored = dedupe_similarity_penalty([score_job(job, DEFAULT_SETTINGS) for job in jobs])
    filtered = filter_scored_jobs(scored, DEFAULT_SETTINGS)
    export_csv(filtered, csv_path)
    export_json(filtered, json_path)
    click.echo(f"Exported {len(filtered)} jobs to {csv_path} and {json_path}")


if __name__ == "__main__":
    cli()
