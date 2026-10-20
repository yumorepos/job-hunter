# Aviation operations workflow

The `job-hunter` CLI already collects and ranks roles from several public sources. Those sources skew toward software jobs and may return broken feeds or incomplete locations. The **aviation shortlist tool** is a complementary, offline, human-reviewed workflow, not a new live scraper.

## 1. Collect & verify leads

Start at employer job boards and manually record each promising role in a private working CSV. Copy `data/aviation_leads_example.csv` as the template. **Do not publish a CSV containing your applications or personal decisions.** The included example names and URLs are fictional fixtures.

Required columns: `title, company, location, posting_date, url, application_status, french_requirement, work_type, evidence_note, eligibility_to_check, checked_at`.

- `application_status`: `review`, `verify_submission`, `applied`, `skip`.
- `french_requirement`: `required`, `not_specified`, `unknown`. `not_specified` does **not** mean French is unnecessary.
- `posting_date`: ISO `YYYY-MM-DD` or blank if not verified.
- `checked_at`: date you last checked the linked posting, not proof that it remains open today.
- URLs must be HTTPS. Employer postings are preferred over aggregators. A search-results link is not proof the exact position remains open.

## 2. Generate a practical shortlist

```bash
python tools/aviation_shortlist.py \
  --input /path/to/private-aviation-leads.csv \
  --output /path/to/private-shortlist.md
```

The tool refuses duplicate company/title/location combinations and invalid statuses, and groups the leads into:

1. New leads to review
2. Verify previous submission first
3. Already applied: follow up
4. Lower priority or known mismatch

The title score is **relevance only**. It cannot verify flight dispatch qualifications, language requirements, citizenship/work authorization, relocation costs, employer hiring status, or the truth of third-party job data.

## 3. Existing CLI: alternate keywords

To try the existing general-purpose scrapers with aviation keywords:

```bash
pip install -e '.[dev]'
job-hunter --config config/aviation-ops.toml scrape
job-hunter --config config/aviation-ops.toml recommend --days 30 --why
```

**Scraper warning:** tech-focused feeds may yield little or no aviation coverage. Indeed RSS in particular can be unavailable. A zero-result scrape is not evidence that no jobs exist. Use the private curated CSV as your actual application tracker.

## 4. Review before applications

Open the employer's site and verify it is still hiring. Check mandatory items (French, licensing, experience, rotational shifts, work location and application deadline). Cross-check the application's existing status before sending another. Use employer instructions for submitting. This repository does not submit applications.

## Safety and privacy

Do not put résumés, passports, personal contact information, passwords, private application notes, or private job-tracker CSVs in this public repository. Avoid circumventing blocked job-board endpoints. No background monitoring or employer application automation is provided.