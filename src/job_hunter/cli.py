from __future__ import annotations

import asyncio
from pathlib import Path
import sqlite3
from typing import cast

import click
import httpx

from .config import Settings, load_settings
from .db import connect, fetch_recent_jobs, job_stats, search_jobs as db_search_jobs, upsert_jobs
from .digest import build_markdown_digest
from .exporters import export_csv, export_json
from .filters import filter_scored_jobs
from .logging_utils import configure_logging
from .models import JobRecord, ScoredJob
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
    transport: httpx.AsyncHTTPTransport | None = None
    if settings.proxy_url:
        transport = httpx.AsyncHTTPTransport(proxy=settings.proxy_url)

    async with httpx.AsyncClient(follow_redirects=True, transport=transport) as client:
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


def _score_recent_jobs(settings: Settings, days: int) -> list[ScoredJob]:
    conn = connect(settings.db_path)
    jobs = _rows_to_jobs(fetch_recent_jobs(conn, days=days))
    conn.close()
    scored = [score_job(job, settings) for job in jobs]
    deduped = dedupe_similarity_penalty(scored, settings)
    return filter_scored_jobs(deduped, settings)


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
    filtered = _score_recent_jobs(settings, days)
    output.write_text(
        build_markdown_digest(filtered, include_reasons=include_reasons), encoding="utf-8"
    )
    click.echo(f"Digest written to {output} ({len(filtered)} jobs)")


@cli.command()
@click.argument("query")
@click.option("--limit", default=20, show_default=True)
@click.option("--company", default=None, help="Filter by company substring")
@click.option("--days", default=None, type=int, help="Only jobs from last N days")
@click.option("--min-score", type=float, default=None)
@click.option("--why/--no-why", default=False, help="Show scoring reasons")
@click.pass_obj
def search(
    settings: Settings,
    query: str,
    limit: int,
    company: str | None,
    days: int | None,
    min_score: float | None,
    why: bool,
) -> None:
    """Search jobs with FTS ranking + fuzzy relevance rerank."""
    conn = connect(settings.db_path)
    rows = db_search_jobs(conn, query, limit=limit * 3, company=company, days=days)
    conn.close()
    if not rows:
        click.echo("No results found. Try broader keywords or a larger --days range.")
        return

    score_floor = min_score if min_score is not None else settings.min_relevance_score
    scored = [score_job(job, settings) for job in _rows_to_jobs(rows)]
    filtered = [
        row
        for row in sorted(scored, key=lambda item: item.score, reverse=True)
        if row.score >= score_floor
    ]

    if not filtered:
        click.echo("Results found, but none met the score threshold. Lower --min-score.")
        return

    for idx, item in enumerate(filtered[:limit], start=1):
        click.echo(
            f"{idx}. [{item.score:>5.1f}] {item.job.title} | {item.job.company} | {item.job.location} | {item.job.url}"
        )
        if why:
            click.echo(f"   why matched: {'; '.join(item.reasons)}")


@cli.command("recommend")
@click.option("--limit", default=10, show_default=True)
@click.option("--days", default=30, show_default=True)
@click.option("--why/--no-why", default=False)
@click.option("--company", default=None, help="Filter recommendations by company substring")
@click.option("--location", default=None, help="Filter recommendations by location substring")
@click.option("--remote-only", is_flag=True, default=False)
@click.option("--min-score", type=float, default=None)
@click.pass_obj
def recommend(
    settings: Settings,
    limit: int,
    days: int,
    why: bool,
    company: str | None,
    location: str | None,
    remote_only: bool,
    min_score: float | None,
) -> None:
    """Recommend the best jobs using preference-aware ranking."""
    scored = _score_recent_jobs(settings, days)
    threshold = min_score if min_score is not None else settings.min_relevance_score
    recommendations = [item for item in scored if item.score >= threshold]

    if company:
        recommendations = [
            item for item in recommendations if company.lower() in item.job.company.lower()
        ]
    if location:
        recommendations = [
            item for item in recommendations if location.lower() in item.job.location.lower()
        ]
    if remote_only:
        recommendations = [item for item in recommendations if item.job.remote_flag]

    if not recommendations:
        click.echo("No recommendations matched the selected filters.")
        return

    click.echo("Recommended Jobs\n")
    for idx, item in enumerate(recommendations[:limit], start=1):
        job = item.job
        click.echo(f"{idx}. {job.title} — {job.company}")
        click.echo(f"   Score: {item.score:.1f}")
        click.echo(f"   Location: {job.location}")
        click.echo(f"   Posted: {job.date_posted}")
        click.echo(f"   Source: {job.source}")
        click.echo(f"   URL: {job.url}")
        if why:
            click.echo("   Why recommended:")
            for reason in item.reasons:
                click.echo(f"   - {reason}")
        click.echo("")


@cli.command("export")
@click.option("--days", default=7, show_default=True)
@click.option("--csv-path", type=click.Path(path_type=Path), default=Path("jobs.csv"))
@click.option("--json-path", type=click.Path(path_type=Path), default=Path("jobs.json"))
@click.pass_obj
def export_cmd(settings: Settings, days: int, csv_path: Path, json_path: Path) -> None:
    """Export recent scored jobs to CSV and JSON."""
    filtered = _score_recent_jobs(settings, days)
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
    click.echo("Top companies hiring:")
    for row in cast(list[sqlite3.Row], metrics["top_companies"]):
        click.echo(f"- {row['company']}: {row['count']}")
    click.echo("Top job locations:")
    for row in cast(list[sqlite3.Row], metrics["top_locations"]):
        click.echo(f"- {row['location']}: {row['count']}")
    click.echo("Remote vs onsite distribution:")
    for row in cast(list[sqlite3.Row], metrics["remote_split"]):
        click.echo(f"- {row['mode']}: {row['count']}")
    click.echo("Most common skills/tags:")
    for tag, count in sorted(tags.items(), key=lambda item: item[1], reverse=True)[:5]:
        click.echo(f"- {tag}: {count}")


if __name__ == "__main__":
    cli()
