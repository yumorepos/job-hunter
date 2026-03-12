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
    assert any("relevance" in reason for reason in scored.reasons)


def test_similarity_penalty_applied_company_variant_title_order():
    settings = Settings(similarity_threshold=0.8)
    older = score_job(
        _job(
            title="Backend Python Engineer",
            company="Shopify Inc.",
            description="Python APIs and distributed systems",
            date_posted="2026-01-01",
            url="https://example.com/job/1",
        ),
        settings,
    )
    newer = score_job(
        _job(
            title="Python Backend Engineer",
            company="Shopify",
            description="Distributed systems and Python APIs",
            date_posted="2026-01-02",
            url="https://example.com/job/2",
        ),
        settings,
    )
    deduped = dedupe_similarity_penalty([older, newer], settings)
    assert len(deduped) == 1
    assert deduped[0].job.url.endswith("2")
