from pathlib import Path

from job_hunter.db import connect, search_jobs, upsert_jobs
from job_hunter.digest import build_markdown_digest
from job_hunter.exporters import export_csv, export_json
from job_hunter.filters import filter_scored_jobs
from job_hunter.models import JobRecord
from job_hunter.scoring import score_job
from job_hunter.config import Settings


def test_db_dedupe_and_search(tmp_path: Path):
    db = tmp_path / "jobs.db"
    conn = connect(db)
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
    assert upsert_jobs(conn, [job]) == 1
    assert upsert_jobs(conn, [job]) == 0
    rows = search_jobs(conn, "python")
    assert rows
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

    csv_path = tmp_path / "jobs.csv"
    json_path = tmp_path / "jobs.json"
    export_csv(scored, csv_path)
    export_json(scored, json_path)
    assert csv_path.exists()
    assert json_path.exists()
