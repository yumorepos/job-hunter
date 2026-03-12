from __future__ import annotations

from .config import Settings
from .models import ScoredJob


def filter_scored_jobs(scored_jobs: list[ScoredJob], settings: Settings) -> list[ScoredJob]:
    return [job for job in scored_jobs if job.score >= settings.min_relevance_score]
