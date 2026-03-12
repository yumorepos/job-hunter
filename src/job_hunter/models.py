from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import re


def _slug(value: str) -> str:
    return re.sub(r"\W+", "", value.lower().strip())


@dataclass(slots=True)
class JobRecord:
    title: str
    company: str
    location: str
    source: str
    url: str
    date_posted: str
    remote_flag: bool
    tags: list[str]
    description: str
    fingerprint: str = ""

    def finalize(self) -> "JobRecord":
        self.title = (self.title or "Untitled Role").strip()
        self.company = (self.company or "Unknown").strip()
        self.location = (self.location or "Unknown").strip()
        self.source = (self.source or "unknown").strip().lower()
        self.url = (self.url or "").strip()
        self.date_posted = normalize_date(self.date_posted)
        self.description = (self.description or "").strip()
        self.tags = sorted({tag.strip().lower() for tag in self.tags if tag and tag.strip()})
        if not self.fingerprint:
            raw = (
                f"{_slug(self.source)}|{_slug(self.company)}|{_slug(self.title)}|{_slug(self.url)}"
            )
            self.fingerprint = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return self


@dataclass(slots=True)
class ScoredJob:
    job: JobRecord
    score: float
    reasons: list[str] = field(default_factory=list)


def normalize_date(value: str | None) -> str:
    if not value:
        return datetime.now(tz=timezone.utc).date().isoformat()
    candidate = value.strip().replace("Z", "+00:00")
    formats = (
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S%z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%d %H:%M:%S",
    )
    for fmt in formats:
        try:
            return datetime.strptime(candidate, fmt).date().isoformat()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(candidate).date().isoformat()
    except ValueError:
        return datetime.now(tz=timezone.utc).date().isoformat()
