from __future__ import annotations

from difflib import SequenceMatcher
import sqlite3
from pathlib import Path

from .config import Settings
from .models import JobRecord
from .utils import normalize_text

SCHEMA_VERSION = 2


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    _migrate(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
    row = conn.execute(
        "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
    ).fetchone()
    current = row["version"] if row else 0

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            location TEXT NOT NULL,
            source TEXT NOT NULL,
            url TEXT NOT NULL,
            date_posted TEXT NOT NULL,
            remote_flag INTEGER NOT NULL DEFAULT 0,
            tags TEXT NOT NULL,
            description TEXT NOT NULL,
            fingerprint TEXT NOT NULL UNIQUE,
            scraped_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_date ON jobs(date_posted)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_fingerprint ON jobs(fingerprint)")

    try:
        conn.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS jobs_fts USING fts5(
                title, company, tags, description, content='jobs', content_rowid='id'
            )
            """
        )
        conn.executescript(
            """
            CREATE TRIGGER IF NOT EXISTS jobs_ai AFTER INSERT ON jobs BEGIN
                INSERT INTO jobs_fts(rowid, title, company, tags, description)
                VALUES (new.id, new.title, new.company, new.tags, new.description);
            END;
            """
        )
    except sqlite3.OperationalError:
        pass

    if current < SCHEMA_VERSION:
        conn.execute("DELETE FROM schema_version")
        conn.execute("INSERT INTO schema_version(version) VALUES (?)", (SCHEMA_VERSION,))
        conn.commit()


def upsert_jobs(
    conn: sqlite3.Connection, jobs: list[JobRecord], settings: Settings | None = None
) -> int:
    active_settings = settings or Settings()
    inserted = 0
    for job in jobs:
        if _has_similar_job(conn, job, active_settings.similarity_threshold):
            continue
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO jobs(title,company,location,source,url,date_posted,remote_flag,tags,description,fingerprint)
            VALUES(?,?,?,?,?,?,?,?,?,?)
            """,
            (
                job.title,
                job.company,
                job.location,
                job.source,
                job.url,
                job.date_posted,
                1 if job.remote_flag else 0,
                ",".join(job.tags),
                job.description,
                job.fingerprint,
            ),
        )
        inserted += cur.rowcount
    conn.commit()
    return inserted


def _has_similar_job(conn: sqlite3.Connection, job: JobRecord, threshold: float) -> bool:
    rows = conn.execute(
        """
        SELECT title, company, description, date_posted
        FROM jobs
        WHERE source = ?
        ORDER BY date_posted DESC
        LIMIT 200
        """,
        (job.source,),
    ).fetchall()
    for row in rows:
        title_sim = SequenceMatcher(
            None, normalize_text(job.title), normalize_text(row["title"])
        ).ratio()
        company_sim = SequenceMatcher(
            None, normalize_text(job.company), normalize_text(row["company"])
        ).ratio()
        desc_sim = SequenceMatcher(
            None,
            normalize_text(job.description[:240]),
            normalize_text((row["description"] or "")[:240]),
        ).ratio()
        if title_sim >= threshold and company_sim >= 0.6 and desc_sim >= 0.65:
            return row["date_posted"] >= job.date_posted
    return False


def fetch_recent_jobs(conn: sqlite3.Connection, days: int = 7) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT * FROM jobs WHERE scraped_at >= datetime('now', ?) ORDER BY scraped_at DESC
        """,
        (f"-{days} day",),
    ).fetchall()


def search_jobs(
    conn: sqlite3.Connection,
    query: str,
    limit: int = 20,
    company: str | None = None,
    days: int | None = None,
) -> list[sqlite3.Row]:
    where = []
    params: list[object] = []
    if company:
        where.append("LOWER(company) LIKE ?")
        params.append(f"%{company.lower()}%")
    if days is not None:
        where.append("date_posted >= date('now', ?)")
        params.append(f"-{days} day")
    where_sql = f"AND {' AND '.join(where)}" if where else ""

    try:
        rows = conn.execute(
            f"""
            SELECT j.*, bm25(jobs_fts) AS rank
            FROM jobs_fts f
            JOIN jobs j ON j.id = f.rowid
            WHERE jobs_fts MATCH ? {where_sql}
            ORDER BY rank ASC, j.date_posted DESC
            LIMIT ?
            """,
            [query, *params, limit * 3],
        ).fetchall()
    except sqlite3.OperationalError:
        pattern = f"%{query}%"
        rows = conn.execute(
            f"""
            SELECT * FROM jobs
            WHERE (title LIKE ? OR company LIKE ? OR tags LIKE ? OR description LIKE ?) {where_sql}
            ORDER BY date_posted DESC
            LIMIT ?
            """,
            [pattern, pattern, pattern, pattern, *params, limit * 3],
        ).fetchall()

    scored = sorted(
        rows,
        key=lambda row: SequenceMatcher(
            None,
            normalize_text(query),
            normalize_text(f"{row['title']} {row['company']} {row['tags']}"),
        ).ratio(),
        reverse=True,
    )
    return scored[:limit]


def job_stats(conn: sqlite3.Connection) -> dict[str, list[sqlite3.Row] | sqlite3.Row | int]:
    total = conn.execute("SELECT COUNT(*) AS total FROM jobs").fetchone()["total"]
    new_today = conn.execute(
        "SELECT COUNT(*) AS total FROM jobs WHERE date_posted = date('now')"
    ).fetchone()["total"]
    top_companies = conn.execute(
        """
        SELECT company, COUNT(*) AS count FROM jobs GROUP BY company ORDER BY count DESC LIMIT 5
        """
    ).fetchall()
    top_locations = conn.execute(
        """
        SELECT location, COUNT(*) AS count FROM jobs GROUP BY location ORDER BY count DESC LIMIT 5
        """
    ).fetchall()
    remote_split = conn.execute(
        """
        SELECT CASE WHEN remote_flag = 1 THEN 'remote' ELSE 'onsite' END AS mode,
               COUNT(*) AS count
        FROM jobs GROUP BY mode ORDER BY count DESC
        """
    ).fetchall()
    return {
        "total": total,
        "new_today": new_today,
        "top_companies": top_companies,
        "top_locations": top_locations,
        "remote_split": remote_split,
    }
