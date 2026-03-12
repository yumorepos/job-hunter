from job_hunter.config import Settings
from job_hunter.models import JobRecord
from job_hunter.scoring import dedupe_similarity_penalty, score_job


def _job(**kwargs):
    base = dict(
        title="Junior Python Backend Developer",
        company="Acme",
        location="Remote Canada",
        source="remoteok",
        url="https://example.com/job/1",
        date_posted="2026-01-01",
        remote_flag=True,
        tags=["python", "backend"],
        description="Python automation data role",
    )
    base.update(kwargs)
    return JobRecord(**base).finalize()


def test_weighted_scoring_reasons():
    settings = Settings(min_relevance_score=0)
    scored = score_job(_job(), settings)
    assert scored.score > settings.min_relevance_score
    assert any("title matched" in reason for reason in scored.reasons)


def test_similarity_penalty_applied_and_newest_preferred():
    settings = Settings()
    older = score_job(_job(url="https://example.com/job/1", date_posted="2026-01-01"), settings)
    newer = score_job(_job(url="https://example.com/job/2", date_posted="2026-01-02"), settings)
    deduped = dedupe_similarity_penalty([older, newer], settings)
    assert len(deduped) == 1
    assert deduped[0].job.url.endswith("2")
