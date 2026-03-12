from job_hunter.models import JobRecord


def test_job_finalize_normalizes_fields_and_tags():
    job = JobRecord(
        title="  Python Engineer  ",
        company="  Acme Inc.  ",
        location="  Remote  ",
        source="RemoteOK",
        url=" https://example.com/role ",
        date_posted="2026-01-01T12:30:00+00:00",
        remote_flag=True,
        tags=[" Python ", "python", "Backend"],
        description=" test ",
    ).finalize()

    assert job.title == "Python Engineer"
    assert job.company == "Acme Inc."
    assert job.source == "remoteok"
    assert job.url == "https://example.com/role"
    assert job.date_posted == "2026-01-01"
    assert job.tags == ["backend", "python"]
    assert len(job.fingerprint) == 64
