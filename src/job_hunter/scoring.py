from __future__ import annotations

from datetime import date, datetime

from .config import Settings
from .models import JobRecord, ScoredJob
from .utils import text_contains_keywords


JUNIOR_HINTS = {"junior", "entry", "intern", "new grad"}


def score_job(job: JobRecord, settings: Settings) -> ScoredJob:
    w = settings.weights
    score = 0.0
    reasons: list[str] = []

    title_matches = text_contains_keywords(job.title, settings.include_keywords)
    if title_matches:
        score += w.title_keyword * len(title_matches)
        reasons.append(f"title matched: {', '.join(title_matches)}")

    desc_matches = text_contains_keywords(job.description, settings.include_keywords)
    if desc_matches:
        score += w.description_keyword * min(3, len(desc_matches))
        reasons.append(f"description matched: {', '.join(desc_matches[:3])}")

    tag_text = " ".join(job.tags)
    tag_matches = text_contains_keywords(tag_text, settings.include_keywords)
    if tag_matches:
        score += w.tag_keyword * len(tag_matches)
        reasons.append(f"tags matched: {', '.join(tag_matches)}")

    role_matches = text_contains_keywords(job.title, settings.preferred_roles)
    if role_matches:
        score += w.preferred_role
        reasons.append("preferred role alignment")

    if job.remote_flag:
        score += w.remote_preference
        reasons.append("remote-friendly")

    if text_contains_keywords(job.location, settings.preferred_locations):
        score += w.location_preference
        reasons.append("preferred location")

    combined = f"{job.title} {job.description}".lower()
    if settings.seniority_target == "junior" and any(h in combined for h in JUNIOR_HINTS):
        score += w.junior_preference
        reasons.append("junior-friendly")

    company_matches = text_contains_keywords(job.company, settings.preferred_companies)
    if company_matches:
        score += w.company_preference
        reasons.append("preferred company")

    excluded = text_contains_keywords(combined, settings.exclude_keywords)
    if excluded:
        score -= 2.5 * len(excluded)
        reasons.append(f"excluded terms: {', '.join(excluded)}")

    try:
        age_days = (date.today() - datetime.fromisoformat(job.date_posted).date()).days
    except ValueError:
        age_days = 0
    if age_days > 0:
        penalty = min(4.0, age_days * w.stale_penalty_per_day)
        score -= penalty
        reasons.append(f"staleness penalty: -{penalty:.1f}")

    return ScoredJob(job=job, score=round(score, 2), reasons=reasons)


def dedupe_similarity_penalty(scored_jobs: list[ScoredJob]) -> list[ScoredJob]:
    seen: set[tuple[str, str]] = set()
    for item in scored_jobs:
        key = (item.job.company.lower(), item.job.title.lower())
        if key in seen:
            item.score -= 1.5
            item.reasons.append("similar duplicate penalty")
        else:
            seen.add(key)
    return scored_jobs
