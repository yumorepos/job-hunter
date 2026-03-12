from __future__ import annotations

import httpx

from ..config import Settings
from ..models import JobRecord
from ..utils import clean_html
from .base import Scraper, fetch_json_with_retry


class RemoteOKScraper(Scraper):
    source = "remoteok"
    url = "https://remoteok.com/api"

    async def scrape(self, client: httpx.AsyncClient, settings: Settings) -> list[JobRecord]:
        data = await fetch_json_with_retry(
            client, self.url, settings, headers={"Accept": "application/json"}
        )
        jobs: list[JobRecord] = []
        for listing in data[1:] if isinstance(data, list) else []:
            if not isinstance(listing, dict):
                continue
            tags = [str(t).lower() for t in (listing.get("tags") or [])]
            job = JobRecord(
                title=listing.get("position") or "",
                company=listing.get("company") or "",
                location="Remote",
                source=self.source,
                url=listing.get("url") or f"https://remoteok.com/jobs/{listing.get('id', '')}",
                date_posted=listing.get("date") or "",
                remote_flag=True,
                tags=tags,
                description=clean_html(listing.get("description") or ""),
            ).finalize()
            jobs.append(job)
        return jobs
