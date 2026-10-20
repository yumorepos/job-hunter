"""Offline aviation job lead triage from human-verified CSV data.

No scraping or applications. A relevance score never means eligibility.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

FIELDS = (
    "title",
    "company",
    "location",
    "posting_date",
    "url",
    "application_status",
    "french_requirement",
    "work_type",
    "evidence_note",
    "eligibility_to_check",
    "checked_at",
)
STATUSES = {"review", "applied", "verify_submission", "skip"}
LANGUAGE = {"required", "not_specified", "unknown"}
PRIORITIES = (
    ("flight operations controller", 11),
    ("dispatcher in training", 11),
    ("network operations coordinator", 10),
    ("flight dispatcher", 10),
    ("flight coordinator", 9),
    ("crew scheduler", 9),
    ("flight follower", 8),
    ("operations analyst", 9),
    ("stoc", 8),
    ("operations coordinator", 8),
    ("crew scheduling supervisor", 4),
)


@dataclass(frozen=True)
class Lead:
    title: str
    company: str
    location: str
    posting_date: str
    url: str
    application_status: str
    french_requirement: str
    work_type: str
    evidence_note: str
    eligibility_to_check: str
    checked_at: str

    def score(self) -> int:
        title = self.title.casefold()
        score = max((score for phrase, score in PRIORITIES if phrase in title), default=3)
        if "supervisor" in title or "manager" in title or "director" in title:
            score -= 5
        if self.work_type.casefold() == "part-time":
            score -= 3
        return score

    def category(self) -> str:
        # Explicit application tracking takes precedence over title ranking.
        if self.application_status == "applied":
            return "Already applied: follow up"
        if self.application_status == "skip" or self.french_requirement == "required":
            return "Lower priority or known mismatch"
        if self.application_status == "verify_submission":
            return "Verify previous submission first"
        return "New leads to review"


def load_leads(path: Path) -> list[Lead]:
    with path.open("r", newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        missing = set(FIELDS) - set(reader.fieldnames or [])
        if missing:
            raise ValueError("CSV is missing columns: " + ", ".join(sorted(missing)))
        leads = []
        seen: set[tuple[str, str, str]] = set()
        for index, row in enumerate(reader, start=2):
            if not any((v or "").strip() for v in row.values() if isinstance(v, str)):
                continue
            normalized = {key: (row.get(key) or "").strip() for key in FIELDS}
            for key in ("title", "company", "location", "url", "checked_at"):
                if not normalized[key]:
                    raise ValueError(f"CSV row {index}: {key} is required")
            parsed = urlparse(normalized["url"])
            if parsed.scheme != "https" or not parsed.hostname:
                raise ValueError(f"CSV row {index}: expected an HTTPS source URL")
            for key in ("checked_at", "posting_date"):
                if normalized[key]:
                    try:
                        date.fromisoformat(normalized[key])
                    except ValueError as exc:
                        raise ValueError(f"CSV row {index}: {key} must be YYYY-MM-DD") from exc
            if normalized["application_status"] not in STATUSES:
                raise ValueError(f"CSV row {index}: invalid application_status")
            if normalized["french_requirement"] not in LANGUAGE:
                raise ValueError(f"CSV row {index}: invalid french_requirement")
            key = tuple(normalized[col].casefold() for col in ("company", "title", "location"))
            if key in seen:
                raise ValueError(f"CSV row {index}: repeated company/title/location")
            seen.add(key)
            leads.append(Lead(**normalized))
    return leads


def make_report(leads: list[Lead], as_of: str) -> str:
    groups = (
        "New leads to review",
        "Verify previous submission first",
        "Already applied: follow up",
        "Lower priority or known mismatch",
    )
    lines = [
        "# Aviation job shortlist",
        "",
        f"As of: {as_of}",
        "",
        "**Status:** manually sourced links; NOT a live job API. Open each employer page to verify it is still recruiting.",
        "**Important:** role-score is relevance only. Credentials, French, experience, work location and application status require human review.",
        "",
    ]
    for group in groups:
        jobs = sorted(
            (j for j in leads if j.category() == group),
            key=lambda j: (-j.score(), j.company.casefold(), j.title.casefold()),
        )
        lines.append(f"## {group} ({len(jobs)})")
        lines.append("")
        if not jobs:
            lines.extend(["No entries.", ""])
            continue
        for job in jobs:
            lines.append(f"### [{job.title} — {job.company}]({job.url})")
            lines.append(f'- Location: {job.location}; work type: {job.work_type or "verify"}')
            lines.append(f"- Relevance: {job.score()}/11 (not an eligibility score)")
            lines.append(
                f'- Posted: {job.posting_date or "not verified"}; last source check: {job.checked_at}'
            )
            lines.append(
                f"- Application: {job.application_status}; French: {job.french_requirement}"
            )
            lines.append(f'- Evidence: {job.evidence_note or "See source"}')
            lines.append(
                f'- Before acting: {job.eligibility_to_check or "Check all mandatory requirements and prior applications"}'
            )
            lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Curated leads CSV")
    parser.add_argument("--output", type=Path, required=True, help="Markdown report")
    parser.add_argument("--as-of", default=date.today().isoformat())
    args = parser.parse_args()
    try:
        date.fromisoformat(args.as_of)
        leads = load_leads(args.input)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(make_report(leads, args.as_of), encoding="utf-8")
    print(f"Wrote {len(leads)} tracked opportunities to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())