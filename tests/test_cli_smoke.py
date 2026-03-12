from pathlib import Path

from click.testing import CliRunner

from job_hunter.cli import cli
from job_hunter.config import Settings
from job_hunter.db import connect, upsert_jobs
from job_hunter.models import JobRecord


def _seed_db(path: Path) -> None:
    conn = connect(path)
    settings = Settings(similarity_threshold=0.8)
    job = JobRecord(
        title="Backend Python Engineer",
        company="Acme",
        location="Remote",
        source="remoteok",
        url="https://example.com/job-1",
        date_posted="2026-03-10",
        remote_flag=True,
        tags=["python", "backend"],
        description="Build backend python systems",
    ).finalize()
    upsert_jobs(conn, [job], settings)
    conn.close()


def test_cli_search_digest_export_stats(tmp_path: Path, monkeypatch):
    db = tmp_path / "jobs.db"
    _seed_db(db)
    monkeypatch.setenv("JOB_HUNTER_DB", str(db))

    runner = CliRunner()

    search_res = runner.invoke(cli, ["search", "python", "--limit", "1"])
    assert search_res.exit_code == 0
    assert "Backend Python Engineer" in search_res.output

    digest_path = tmp_path / "digest.md"
    digest_res = runner.invoke(cli, ["digest", "--days", "3650", "--output", str(digest_path)])
    assert digest_res.exit_code == 0
    assert digest_path.exists()

    csv_path = tmp_path / "jobs.csv"
    json_path = tmp_path / "jobs.json"
    export_res = runner.invoke(
        cli,
        [
            "export",
            "--days",
            "3650",
            "--csv-path",
            str(csv_path),
            "--json-path",
            str(json_path),
        ],
    )
    assert export_res.exit_code == 0
    assert csv_path.exists()
    assert json_path.exists()

    stats_res = runner.invoke(cli, ["stats"])
    assert stats_res.exit_code == 0
    assert "Total jobs collected" in stats_res.output
