from __future__ import annotations

import httpx

from ..config import Settings
from ..models import JobRecord
from ..utils import clean_html
from .base import Scraper, fetch_json_with_retry


class ArbeitnowScraper(Scraper):
    source = "arbeitnow"
    base_url = "https://www.arbeitnow.com/api/job-board-api"

    async def scrape(self, client: httpx.AsyncClient, settings: Settings) -> list[JobRecord]:
        jobs: list[JobRecord] = []
        for page in range(1, 4):
            data = await fetch_json_with_retry(client, f"{self.base_url}?page={page}", settings)
            listings = data.get("data", []) if isinstance(data, dict) else []
            if not listings:
                break
            for listing in listings:
                if not isinstance(listing, dict):
                    continue
                location = listing.get("location") or "Unknown"
                title = listing.get("title") or ""
                job = JobRecord(
                    title=title,
                    company=listing.get("company_name") or "",
                    location=location,
                    source=self.source,
                    url=listing.get("url") or "",
                    date_posted=listing.get("created_at") or "",
                    remote_flag="remote" in f"{location} {title}".lower(),
                    tags=[str(t) for t in listing.get("tags") or []],
                    description=clean_html(listing.get("description") or ""),
                ).finalize()
                if job.url:
                    jobs.append(job)
        return jobs
