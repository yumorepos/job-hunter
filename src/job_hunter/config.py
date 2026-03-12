from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os


@dataclass(slots=True)
class ScoringWeights:
    title_keyword: float = 4.0
    description_keyword: float = 2.0
    tag_keyword: float = 3.0
    preferred_role: float = 3.0
    remote_preference: float = 2.0
    location_preference: float = 2.0
    junior_preference: float = 1.5
    company_preference: float = 2.0
    stale_penalty_per_day: float = 0.2


@dataclass(slots=True)
class Settings:
    db_path: Path = Path(os.getenv("JOB_HUNTER_DB", "jobs.db"))
    digest_path: Path = Path(os.getenv("JOB_HUNTER_DIGEST_PATH", "digest.md"))
    request_timeout: float = float(os.getenv("JOB_HUNTER_TIMEOUT", "15"))
    max_retries: int = int(os.getenv("JOB_HUNTER_MAX_RETRIES", "2"))
    backoff_seconds: float = float(os.getenv("JOB_HUNTER_BACKOFF", "0.7"))

    include_keywords: list[str] = field(
        default_factory=lambda: ["python", "data", "automation", "backend", "developer"]
    )
    exclude_keywords: list[str] = field(default_factory=lambda: ["senior", "staff", "principal"])
    preferred_locations: list[str] = field(default_factory=lambda: ["remote", "canada", "montreal"])
    preferred_roles: list[str] = field(
        default_factory=lambda: ["python developer", "data analyst", "automation"]
    )
    preferred_companies: list[str] = field(default_factory=list)
    seniority_target: str = os.getenv("JOB_HUNTER_SENIORITY", "junior")
    min_relevance_score: float = float(os.getenv("JOB_HUNTER_MIN_SCORE", "3"))

    weights: ScoringWeights = field(default_factory=ScoringWeights)


DEFAULT_SETTINGS = Settings()
