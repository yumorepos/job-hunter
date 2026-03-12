from __future__ import annotations

from collections import defaultdict
from datetime import date

from .models import ScoredJob


def build_markdown_digest(results: list[ScoredJob], include_reasons: bool = True) -> str:
    lines = [f"# Job Digest — {date.today().isoformat()}", f"> {len(results)} matching job(s)", ""]
    grouped: dict[str, list[ScoredJob]] = defaultdict(list)
    for row in sorted(results, key=lambda s: s.score, reverse=True):
        bucket = (
            "High Relevance"
            if row.score >= 9
            else "Medium Relevance" if row.score >= 6 else "Low Relevance"
        )
        grouped[bucket].append(row)

    for bucket in ["High Relevance", "Medium Relevance", "Low Relevance"]:
        rows = grouped.get(bucket, [])
        if not rows:
            continue
        lines.append(f"## {bucket} ({len(rows)})")
        for item in rows:
            job = item.job
            lines.append(f"### [{job.title}]({job.url})")
            lines.append(f"- Company: {job.company}")
            lines.append(f"- Location: {job.location}")
            lines.append(f"- Source: {job.source}")
            lines.append(f"- Posted: {job.date_posted}")
            lines.append(f"- Score: {item.score}")
            if include_reasons and item.reasons:
                lines.append(f"- Why matched: {'; '.join(item.reasons)}")
            lines.append("")
    return "\n".join(lines)
