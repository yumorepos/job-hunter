from __future__ import annotations

import sqlite3
from pathlib import Path

from .models import JobRecord

SCHEMA_VERSION = 1


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
    if current >= SCHEMA_VERSION:
        return

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

    conn.execute("DELETE FROM schema_version")
    conn.execute("INSERT INTO schema_version(version) VALUES (?)", (SCHEMA_VERSION,))
    conn.commit()


def upsert_jobs(conn: sqlite3.Connection, jobs: list[JobRecord]) -> int:
    inserted = 0
    for job in jobs:
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


def fetch_recent_jobs(conn: sqlite3.Connection, days: int = 7) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT * FROM jobs WHERE scraped_at >= datetime('now', ?) ORDER BY scraped_at DESC
        """,
        (f"-{days} day",),
    ).fetchall()


def search_jobs(conn: sqlite3.Connection, query: str, limit: int = 20) -> list[sqlite3.Row]:
    try:
        return conn.execute(
            """
            SELECT j.* FROM jobs_fts f
            JOIN jobs j ON j.id = f.rowid
            WHERE jobs_fts MATCH ?
            ORDER BY j.scraped_at DESC LIMIT ?
            """,
            (query, limit),
        ).fetchall()
    except sqlite3.OperationalError:
        pattern = f"%{query}%"
        return conn.execute(
            """
            SELECT * FROM jobs WHERE title LIKE ? OR company LIKE ? OR tags LIKE ? OR description LIKE ?
            ORDER BY scraped_at DESC LIMIT ?
            """,
            (pattern, pattern, pattern, pattern, limit),
        ).fetchall()
