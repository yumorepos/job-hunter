from __future__ import annotations

import asyncio
from pathlib import Path

import click
import httpx

from .config import Settings, load_settings
from .db import (
    connect,
    fetch_recent_jobs,
    job_stats,
    search_jobs as db_search_jobs,
    upsert_jobs,
)
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
    client_kwargs: dict[str, object] = {"follow_redirects": True}
    if settings.proxy_url:
        client_kwargs["transport"] = httpx.AsyncHTTPTransport(proxy=settings.proxy_url)

    async with httpx.AsyncClient(**client_kwargs) as client:
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
        stats[source] = upsert_jobs(conn, jobs, settings)
    conn.close()
    return stats, failures


@click.group()
@click.option("--verbose", is_flag=True, default=False)
@click.option(
    "--config", "config_path", type=click.Path(path_type=Path), default=Path("config.toml")
)
@click.option("--min-score", type=float, default=None)
@click.option("--keyword", "keywords", multiple=True)
@click.option("--exclude", "excludes", multiple=True)
@click.option("--location", "locations", multiple=True)
def cli(
    verbose: bool,
    config_path: Path,
    min_score: float | None,
    keywords: tuple[str, ...],
    excludes: tuple[str, ...],
    locations: tuple[str, ...],
) -> None:
    """Job Hunter CLI."""
    configure_logging(verbose)
    overrides = {
        "min_relevance_score": min_score,
        "include_keywords": list(keywords) or None,
        "exclude_keywords": list(excludes) or None,
        "preferred_locations": list(locations) or None,
    }
    click.get_current_context().obj = load_settings(
        config_path=config_path, cli_overrides=overrides
    )


@cli.command()
@click.pass_obj
def scrape(settings: Settings) -> None:
    """Scrape all sources and persist normalized jobs."""
    stats, failures = asyncio.run(scrape_all(settings))
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
@click.pass_obj
def digest(settings: Settings, days: int, output: Path, include_reasons: bool) -> None:
    """Generate markdown digest from recent jobs."""
    conn = connect(settings.db_path)
    jobs = _rows_to_jobs(fetch_recent_jobs(conn, days=days))
    conn.close()
    scored = dedupe_similarity_penalty([score_job(job, settings) for job in jobs], settings)
    filtered = filter_scored_jobs(scored, settings)
    output.write_text(
        build_markdown_digest(filtered, include_reasons=include_reasons), encoding="utf-8"
    )
    click.echo(f"Digest written to {output} ({len(filtered)} jobs)")


@cli.command()
@click.argument("query")
@click.option("--limit", default=20, show_default=True)
@click.option("--company", default=None, help="Filter by company substring")
@click.option("--days", default=None, type=int, help="Only jobs from last N days")
@click.option("--why/--no-why", default=False, help="Show scoring reasons")
@click.pass_obj
def search(
    settings: Settings, query: str, limit: int, company: str | None, days: int | None, why: bool
) -> None:
    """Search jobs with FTS ranking + fuzzy relevance rerank."""
    conn = connect(settings.db_path)
    rows = db_search_jobs(conn, query, limit=limit, company=company, days=days)
    conn.close()
    if not rows:
        click.echo("No results")
        return
    scored = [score_job(job, settings) for job in _rows_to_jobs(rows)]
    for idx, item in enumerate(sorted(scored, key=lambda row: row.score, reverse=True), start=1):
        click.echo(
            f"{idx}. [{item.score:>5.1f}] {item.job.title} | {item.job.company} | {item.job.location} | {item.job.url}"
        )
        if why:
            click.echo(f"   why: {'; '.join(item.reasons)}")


@cli.command("export")
@click.option("--days", default=7, show_default=True)
@click.option("--csv-path", type=click.Path(path_type=Path), default=Path("jobs.csv"))
@click.option("--json-path", type=click.Path(path_type=Path), default=Path("jobs.json"))
@click.pass_obj
def export_cmd(settings: Settings, days: int, csv_path: Path, json_path: Path) -> None:
    """Export recent scored jobs to CSV and JSON."""
    conn = connect(settings.db_path)
    jobs = _rows_to_jobs(fetch_recent_jobs(conn, days=days))
    conn.close()
    scored = dedupe_similarity_penalty([score_job(job, settings) for job in jobs], settings)
    filtered = filter_scored_jobs(scored, settings)
    export_csv(filtered, csv_path)
    export_json(filtered, json_path)
    click.echo(f"Exported {len(filtered)} jobs -> {csv_path}, {json_path}")


@cli.command()
@click.pass_obj
def stats(settings: Settings) -> None:
    """Show market intelligence metrics from the local database."""
    conn = connect(settings.db_path)
    metrics = job_stats(conn)
    rows = fetch_recent_jobs(conn, days=30)
    conn.close()

    tags: dict[str, int] = {}
    for row in rows:
        for tag in (row["tags"] or "").split(","):
            if tag:
                tags[tag] = tags.get(tag, 0) + 1

    click.echo(f"Total jobs collected: {metrics['total']}")
    click.echo(f"New jobs today: {metrics['new_today']}")
    click.echo("Top companies:")
    for row in metrics["top_companies"]:
        click.echo(f"- {row['company']}: {row['count']}")
    click.echo("Top locations:")
    for row in metrics["top_locations"]:
        click.echo(f"- {row['location']}: {row['count']}")
    click.echo("Remote vs onsite:")
    for row in metrics["remote_split"]:
        click.echo(f"- {row['mode']}: {row['count']}")
    click.echo("Top skills/tags:")
    for tag, count in sorted(tags.items(), key=lambda item: item[1], reverse=True)[:5]:
        click.echo(f"- {tag}: {count}")


if __name__ == "__main__":
    cli()
