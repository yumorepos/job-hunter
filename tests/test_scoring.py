from job_hunter.config import Settings
from job_hunter.models import JobRecord
from job_hunter.scoring import dedupe_similarity_penalty, score_job


def _job(**kwargs):
    base = dict(
        title="Junior Python Developer",
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
    settings = Settings()
    scored = score_job(_job(), settings)
    assert scored.score > settings.min_relevance_score
    assert scored.reasons


def test_similarity_penalty_applied():
    settings = Settings()
    one = score_job(_job(url="https://example.com/job/1"), settings)
    two = score_job(_job(url="https://example.com/job/2"), settings)
    deduped = dedupe_similarity_penalty([one, two])
    assert deduped[1].score < deduped[0].score
