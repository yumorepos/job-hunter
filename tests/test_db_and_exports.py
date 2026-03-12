from pathlib import Path

from job_hunter.config import Settings
from job_hunter.db import connect, job_stats, search_jobs, upsert_jobs
from job_hunter.digest import build_markdown_digest
from job_hunter.exporters import export_csv, export_json
from job_hunter.filters import filter_scored_jobs
from job_hunter.models import JobRecord
from job_hunter.scoring import score_job


def test_db_dedupe_and_search(tmp_path: Path):
    db = tmp_path / "jobs.db"
    conn = connect(db)
    settings = Settings(similarity_threshold=0.8)
    one = JobRecord(
        title="Python Developer",
        company="Acme",
        location="Remote",
        source="remoteok",
        url="https://example.com/1",
        date_posted="2026-01-01",
        remote_flag=True,
        tags=["python"],
        description="Automation role",
    ).finalize()
    two = JobRecord(
        title="Python Developer",
        company="Acme Inc",
        location="Remote",
        source="remoteok",
        url="https://example.com/2",
        date_posted="2025-01-01",
        remote_flag=True,
        tags=["python"],
        description="Automation role",
    ).finalize()
    assert upsert_jobs(conn, [one], settings) == 1
    assert upsert_jobs(conn, [two], settings) == 0
    rows = search_jobs(conn, "python", company="acme", days=4000)
    assert rows
    assert job_stats(conn)["total"] == 1
    conn.close()


def test_digest_and_exports(tmp_path: Path):
    settings = Settings(min_relevance_score=0)
    job = JobRecord(
        title="Python Developer",
        company="Acme",
        location="Remote",
        source="remoteok",
        url="https://example.com/1",
        date_posted="2026-01-01",
        remote_flag=True,
        tags=["python"],
        description="Automation role",
    ).finalize()
    scored = filter_scored_jobs([score_job(job, settings)], settings)
    digest = build_markdown_digest(scored)
    assert "Why matched" in digest
    assert "Score" in digest

    csv_path = tmp_path / "jobs.csv"
    json_path = tmp_path / "jobs.json"
    export_csv(scored, csv_path)
    export_json(scored, json_path)
    assert csv_path.exists()
    assert json_path.exists()
