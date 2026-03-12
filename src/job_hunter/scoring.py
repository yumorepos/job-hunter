from __future__ import annotations

from datetime import date, datetime

from .config import Settings
from .models import JobRecord, ScoredJob
from .utils import similarity_ratio, text_contains_keywords

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
        score += w.description_keyword * min(4, len(desc_matches))
        reasons.append(f"description matched: {', '.join(desc_matches[:4])}")

    tag_text = " ".join(job.tags)
    tag_matches = text_contains_keywords(tag_text, settings.include_keywords)
    if tag_matches:
        score += w.tag_keyword * len(tag_matches)
        reasons.append(f"skills matched: {', '.join(tag_matches)}")

    if text_contains_keywords(job.title, settings.preferred_roles):
        score += w.preferred_role
        reasons.append("preferred role alignment")

    if job.remote_flag:
        score += w.remote_preference
        reasons.append("remote preference")

    if text_contains_keywords(job.location, settings.preferred_locations):
        score += w.location_preference
        reasons.append("preferred location")

    combined = f"{job.title} {job.description}".lower()
    if settings.seniority_target == "junior" and any(hint in combined for hint in JUNIOR_HINTS):
        score += w.junior_preference
        reasons.append("junior-friendly")

    if text_contains_keywords(job.company, settings.preferred_companies):
        score += w.company_preference
        reasons.append("preferred company")

    excluded = text_contains_keywords(combined, settings.exclude_keywords)
    if excluded:
        score -= 2.5 * len(excluded)
        reasons.append(f"excluded terms: {', '.join(excluded)}")

    age_days = _job_age_days(job.date_posted)
    if age_days <= 2:
        score += w.freshness_boost
        reasons.append("fresh posting")
    elif age_days > 2:
        penalty = min(5.0, age_days * w.stale_penalty_per_day)
        score -= penalty
        reasons.append(f"staleness penalty: -{penalty:.1f}")

    return ScoredJob(job=job, score=round(score, 2), reasons=reasons)


def dedupe_similarity_penalty(scored_jobs: list[ScoredJob], settings: Settings) -> list[ScoredJob]:
    ranked = sorted(scored_jobs, key=lambda item: item.job.date_posted, reverse=True)
    selected: list[ScoredJob] = []
    for item in ranked:
        duplicate = _find_similar(item, selected, settings.similarity_threshold)
        if duplicate:
            item.score -= settings.weights.duplicate_penalty
            item.reasons.append("duplicate similarity penalty")
            if item.job.date_posted >= duplicate.job.date_posted:
                selected.remove(duplicate)
                selected.append(item)
            continue
        selected.append(item)
    return sorted(selected, key=lambda item: item.score, reverse=True)


def _find_similar(
    candidate: ScoredJob, existing: list[ScoredJob], threshold: float
) -> ScoredJob | None:
    for row in existing:
        title_sim = similarity_ratio(candidate.job.title, row.job.title)
        company_sim = similarity_ratio(candidate.job.company, row.job.company)
        desc_sim = similarity_ratio(candidate.job.description[:300], row.job.description[:300])
        if title_sim >= threshold and company_sim >= 0.8 and desc_sim >= 0.6:
            return row
    return None


def _job_age_days(raw_date: str) -> int:
    try:
        return (date.today() - datetime.fromisoformat(raw_date).date()).days
    except ValueError:
        return 0
