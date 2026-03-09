"""
Job Hunter - A Python job scraper for Python/data/automation roles.

Scrapes public job boards, filters by keywords, stores in SQLite,
and generates markdown digests. Built for a Montreal-based developer.
"""

import asyncio
import sqlite3
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

import click
import httpx
from rich.console import Console
from rich.table import Table
from rich import box

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DB_PATH = Path("jobs.db")

KEYWORDS = ["python", "data analyst", "automation", "junior developer", "junior dev"]

SOURCES = {
    "indeed": "https://ca.indeed.com/rss",
    "remoteok": "https://remoteok.com/api",
    "arbeitnow": "https://www.arbeitnow.com/api/job-board-api",
    "hackernews": "https://hn.algolia.com/api/v1/search",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; JobHunterBot/1.0; "
        "+https://github.com/yourusername/job-hunter)"
    )
}

console = Console()


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------


def init_db(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Initialise the SQLite database and create tables if needed."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT    NOT NULL,
            company     TEXT,
            location    TEXT,
            url         TEXT    UNIQUE NOT NULL,
            source      TEXT    NOT NULL,
            tags        TEXT,
            description TEXT,
            posted_at   TEXT,
            scraped_at  TEXT    NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    return conn


def upsert_job(conn: sqlite3.Connection, job: dict) -> bool:
    """Insert a job; skip duplicates (keyed on URL). Returns True if new."""
    try:
        conn.execute(
            """
            INSERT INTO jobs (title, company, location, url, source, tags,
                              description, posted_at)
            VALUES (:title, :company, :location, :url, :source, :tags,
                    :description, :posted_at)
            """,
            job,
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # URL already exists — duplicate, skip silently
        return False


# ---------------------------------------------------------------------------
# Scrapers
# ---------------------------------------------------------------------------


async def scrape_indeed(client: httpx.AsyncClient) -> list[dict]:
    """
    Scrape Indeed Canada RSS feed for each keyword.

    Indeed exposes an RSS endpoint at ca.indeed.com/rss that accepts
    a ``q`` (query) parameter and returns standard RSS 2.0 XML.
    """
    jobs: list[dict] = []

    for keyword in KEYWORDS:
        params = {"q": keyword, "l": "Canada", "sort": "date"}
        url = f"{SOURCES['indeed']}?{urlencode(params)}"
        try:
            resp = await client.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            console.print(f"[yellow]Indeed ({keyword}): {exc}[/yellow]")
            continue

        try:
            root = ET.fromstring(resp.text)
        except ET.ParseError as exc:
            console.print(f"[yellow]Indeed XML parse error ({keyword}): {exc}[/yellow]")
            continue

        ns = {"dc": "http://purl.org/dc/elements/1.1/"}
        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            desc = (item.findtext("description") or "").strip()
            pub_date = (item.findtext("pubDate") or "").strip()
            location = (item.findtext("location") or "").strip()
            company = (
                item.findtext("source") or item.findtext("dc:creator", namespaces=ns) or ""
            ).strip()

            if not link:
                continue

            jobs.append({
                "title": title,
                "company": company,
                "location": location or "Canada",
                "url": link,
                "source": "indeed",
                "tags": keyword,
                "description": desc[:500],
                "posted_at": pub_date,
            })

    return jobs


async def scrape_remoteok(client: httpx.AsyncClient) -> list[dict]:
    """
    Scrape RemoteOK JSON API.

    The first element of the response array is metadata; skip it.
    Filter listings by matching KEYWORDS against title and tags.
    """
    jobs: list[dict] = []
    try:
        resp = await client.get(
            SOURCES["remoteok"],
            headers={**HEADERS, "Accept": "application/json"},
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        console.print(f"[yellow]RemoteOK: {exc}[/yellow]")
        return jobs

    for listing in data[1:]:  # skip metadata header
        if not isinstance(listing, dict):
            continue

        title = (listing.get("position") or "").lower()
        tags = [t.lower() for t in (listing.get("tags") or [])]
        combined = title + " " + " ".join(tags)

        matched = [kw for kw in KEYWORDS if kw in combined]
        if not matched:
            continue

        jobs.append({
            "title": listing.get("position", ""),
            "company": listing.get("company", ""),
            "location": "Remote",
            "url": listing.get("url") or f"https://remoteok.com/jobs/{listing.get('id', '')}",
            "source": "remoteok",
            "tags": ", ".join(listing.get("tags") or []),
            "description": (listing.get("description") or "")[:500],
            "posted_at": listing.get("date", ""),
        })

    return jobs


async def scrape_arbeitnow(client: httpx.AsyncClient) -> list[dict]:
    """
    Scrape Arbeitnow job board API (no auth required).

    Paginates through up to 3 pages and filters by KEYWORDS.
    """
    jobs: list[dict] = []

    for page in range(1, 4):
        url = f"{SOURCES['arbeitnow']}?page={page}"
        try:
            resp = await client.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            console.print(f"[yellow]Arbeitnow page {page}: {exc}[/yellow]")
            break

        listings = data.get("data", [])
        if not listings:
            break

        for listing in listings:
            title = (listing.get("title") or "").lower()
            tags = [t.lower() for t in (listing.get("tags") or [])]
            desc = (listing.get("description") or "").lower()
            combined = title + " " + " ".join(tags) + " " + desc[:300]

            matched = [kw for kw in KEYWORDS if kw in combined]
            if not matched:
                continue

            jobs.append({
                "title": listing.get("title", ""),
                "company": listing.get("company_name", ""),
                "location": listing.get("location", "Remote"),
                "url": listing.get("url", ""),
                "source": "arbeitnow",
                "tags": ", ".join(listing.get("tags") or []),
                "description": (listing.get("description") or "")[:500],
                "posted_at": listing.get("created_at", ""),
            })

    return jobs


async def scrape_hackernews(client: httpx.AsyncClient) -> list[dict]:
    """
    Scrape HackerNews 'Who's Hiring' threads via the Algolia HN API.

    Searches the latest monthly thread comments for KEYWORDS.
    """
    jobs: list[dict] = []

    # Find the most recent "Ask HN: Who is hiring?" thread
    search_url = SOURCES["hackernews"]
    try:
        resp = await client.get(
            search_url,
            params={
                "query": "Ask HN: Who is hiring?",
                "tags": "story,ask_hn",
                "hitsPerPage": 1,
            },
            headers=HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        hits = resp.json().get("hits", [])
    except (httpx.HTTPError, ValueError) as exc:
        console.print(f"[yellow]HackerNews (thread search): {exc}[/yellow]")
        return jobs

    if not hits:
        return jobs

    thread_id = hits[0].get("objectID")

    # Fetch top-level comments from that thread for each keyword
    for keyword in KEYWORDS:
        try:
            resp = await client.get(
                search_url,
                params={
                    "query": keyword,
                    "tags": f"comment,story_{thread_id}",
                    "hitsPerPage": 20,
                },
                headers=HEADERS,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            console.print(f"[yellow]HackerNews ({keyword}): {exc}[/yellow]")
            continue

        for hit in data.get("hits", []):
            comment_text = hit.get("comment_text") or hit.get("story_text") or ""
            obj_id = hit.get("objectID", "")
            url = f"https://news.ycombinator.com/item?id={obj_id}"

            # Extract a rough title from the first line of the comment
            first_line = comment_text.strip().split("\n")[0][:120]
            title = first_line if first_line else f"HN Hiring — {keyword}"

            created_at = hit.get("created_at", "")

            jobs.append({
                "title": title,
                "company": "",
                "location": "Remote / Various",
                "url": url,
                "source": "hackernews",
                "tags": keyword,
                "description": comment_text[:500],
                "posted_at": created_at,
            })

    return jobs


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


async def run_scrape(db_path: Path = DB_PATH) -> dict[str, int]:
    """
    Run all scrapers concurrently and persist results.

    Returns a dict mapping source name → number of new jobs inserted.
    """
    conn = init_db(db_path)
    stats: dict[str, int] = {}

    async with httpx.AsyncClient(follow_redirects=True) as client:
        results = await asyncio.gather(
            scrape_indeed(client),
            scrape_remoteok(client),
            scrape_arbeitnow(client),
            scrape_hackernews(client),
            return_exceptions=True,
        )

    source_names = ["indeed", "remoteok", "arbeitnow", "hackernews"]

    for source, result in zip(source_names, results):
        if isinstance(result, Exception):
            console.print(f"[red]Scraper '{source}' failed: {result}[/red]")
            stats[source] = 0
            continue

        new_count = sum(upsert_job(conn, job) for job in result)
        stats[source] = new_count

    conn.close()
    return stats


def build_digest(
    db_path: Path = DB_PATH,
    days: int = 1,
) -> str:
    """
    Generate a Markdown digest of jobs scraped in the last ``days`` days.

    Returns the digest as a string.
    """
    conn = init_db(db_path)
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

    rows = conn.execute(
        """
        SELECT title, company, location, url, source, tags, scraped_at
        FROM jobs
        WHERE scraped_at >= ?
        ORDER BY scraped_at DESC
        """,
        (cutoff,),
    ).fetchall()
    conn.close()

    today = datetime.utcnow().strftime("%Y-%m-%d")
    lines = [
        f"# Job Digest — {today}",
        f"> {len(rows)} listing(s) found in the last {days} day(s)\n",
        "---\n",
    ]

    if not rows:
        lines.append("_No new jobs found. Try running `job-hunter scrape` first._\n")
        return "\n".join(lines)

    # Group by source
    by_source: dict[str, list] = {}
    for row in rows:
        by_source.setdefault(row["source"], []).append(row)

    for source, listings in by_source.items():
        lines.append(f"## {source.title()} ({len(listings)})\n")
        for j in listings:
            company_str = f" — {j['company']}" if j["company"] else ""
            location_str = f" `{j['location']}`" if j["location"] else ""
            lines.append(f"### [{j['title']}]({j['url']})")
            lines.append(f"{company_str}{location_str}  ")
            if j["tags"]:
                lines.append(f"**Tags:** {j['tags']}  ")
            lines.append(f"*Scraped:* {j['scraped_at'][:10]}\n")

    return "\n".join(lines)


def search_jobs(
    query: str,
    db_path: Path = DB_PATH,
    limit: int = 20,
) -> list[sqlite3.Row]:
    """Full-text search across title, company, tags, and description."""
    conn = init_db(db_path)
    pattern = f"%{query}%"
    rows = conn.execute(
        """
        SELECT title, company, location, url, source, tags, scraped_at
        FROM jobs
        WHERE title       LIKE ?
           OR company     LIKE ?
           OR tags        LIKE ?
           OR description LIKE ?
        ORDER BY scraped_at DESC
        LIMIT ?
        """,
        (pattern, pattern, pattern, pattern, limit),
    ).fetchall()
    conn.close()
    return rows


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@click.group()
@click.version_option("1.0.0", prog_name="job-hunter")
def cli() -> None:
    """Job Hunter — scrape, search, and digest job listings from your terminal."""


@cli.command()
def scrape() -> None:
    """Scrape all configured job sources and store new listings."""
    console.print("[bold cyan]Job Hunter[/bold cyan] — starting scrape...\n")

    stats = asyncio.run(run_scrape())

    table = Table(title="Scrape Results", box=box.ROUNDED, show_lines=False)
    table.add_column("Source", style="cyan", no_wrap=True)
    table.add_column("New Jobs", style="green", justify="right")

    total = 0
    for source, count in stats.items():
        table.add_row(source.title(), str(count))
        total += count

    table.add_section()
    table.add_row("[bold]Total[/bold]", f"[bold]{total}[/bold]")
    console.print(table)

    if total:
        console.print(f"\n[green]✓ {total} new job(s) saved to {DB_PATH}[/green]")
    else:
        console.print("\n[yellow]No new jobs found (all already in database).[/yellow]")


@cli.command()
@click.option("--days", default=1, show_default=True, help="Days to look back.")
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="Save digest to a file (Markdown).",
)
def digest(days: int, output: Optional[str]) -> None:
    """Generate a Markdown digest of recently scraped jobs."""
    md = build_digest(days=days)

    if output:
        Path(output).write_text(md, encoding="utf-8")
        console.print(f"[green]Digest saved to {output}[/green]")
    else:
        from rich.markdown import Markdown
        console.print(Markdown(md))


@cli.command()
@click.argument("query")
@click.option("--limit", default=20, show_default=True, help="Max results to show.")
def search(query: str, limit: int) -> None:
    """Search stored jobs by keyword (title, company, tags, description)."""
    rows = search_jobs(query, limit=limit)

    if not rows:
        console.print(f"[yellow]No jobs found matching '{query}'.[/yellow]")
        return

    table = Table(
        title=f"Results for '{query}' ({len(rows)} found)",
        box=box.SIMPLE_HEAVY,
        show_lines=True,
    )
    table.add_column("#", style="dim", width=4)
    table.add_column("Title", style="bold white", max_width=40)
    table.add_column("Company", style="cyan", max_width=20)
    table.add_column("Location", style="magenta", max_width=18)
    table.add_column("Source", style="yellow", width=12)
    table.add_column("Date", style="dim", width=10)

    for i, row in enumerate(rows, 1):
        table.add_row(
            str(i),
            row["title"],
            row["company"] or "—",
            row["location"] or "—",
            row["source"],
            row["scraped_at"][:10],
        )

    console.print(table)
    console.print("\n[dim]URLs:[/dim]")
    for i, row in enumerate(rows, 1):
        console.print(f"  [dim]{i}.[/dim] {row['url']}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cli()
