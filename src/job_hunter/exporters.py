from __future__ import annotations

import csv
import json
from pathlib import Path

from .models import ScoredJob


def export_csv(results: list[ScoredJob], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "title",
                "company",
                "location",
                "source",
                "url",
                "date_posted",
                "remote_flag",
                "tags",
                "description",
                "score",
                "reasons",
            ],
        )
        writer.writeheader()
        for row in results:
            writer.writerow(
                {
                    "title": row.job.title,
                    "company": row.job.company,
                    "location": row.job.location,
                    "source": row.job.source,
                    "url": row.job.url,
                    "date_posted": row.job.date_posted,
                    "remote_flag": row.job.remote_flag,
                    "tags": ",".join(row.job.tags),
                    "description": row.job.description,
                    "score": row.score,
                    "reasons": " | ".join(row.reasons),
                }
            )


def export_json(results: list[ScoredJob], path: Path) -> None:
    payload = [
        {
            "title": row.job.title,
            "company": row.job.company,
            "location": row.job.location,
            "source": row.job.source,
            "url": row.job.url,
            "date_posted": row.job.date_posted,
            "remote_flag": row.job.remote_flag,
            "tags": row.job.tags,
            "description": row.job.description,
            "fingerprint": row.job.fingerprint,
            "score": row.score,
            "reasons": row.reasons,
        }
        for row in results
    ]
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
