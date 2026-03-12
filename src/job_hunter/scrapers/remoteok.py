from __future__ import annotations

import logging

import httpx

from ..config import Settings
from ..models import JobRecord
from ..utils import clean_html, extract_links_from_html
from .base import Scraper, fetch_json_with_retry, fetch_text_with_retry

LOGGER = logging.getLogger(__name__)


class RemoteOKScraper(Scraper):
    source = "remoteok"
    url = "https://remoteok.com/api"

    async def scrape(self, client: httpx.AsyncClient, settings: Settings) -> list[JobRecord]:
        jobs: list[JobRecord] = []
        try:
            data = await fetch_json_with_retry(
                client, self.url, settings, headers={"Accept": "application/json"}
            )
            listings = data[1:] if isinstance(data, list) else []
            for listing in listings:
                if not isinstance(listing, dict):
                    continue
                tags = [str(t).lower() for t in (listing.get("tags") or [])]
                jobs.append(
                    JobRecord(
                        title=listing.get("position") or "",
                        company=listing.get("company") or "",
                        location="Remote",
                        source=self.source,
                        url=listing.get("url")
                        or f"https://remoteok.com/jobs/{listing.get('id', '')}",
                        date_posted=listing.get("date") or "",
                        remote_flag=True,
                        tags=tags,
                        description=clean_html(listing.get("description") or ""),
                    ).finalize()
                )
            if jobs:
                return jobs
        except RuntimeError as exc:
            LOGGER.info("remoteok_api_failed", extra={"error": str(exc)})

        html = await fetch_text_with_retry(client, "https://remoteok.com/remote-dev-jobs", settings)
        for link, title in extract_links_from_html(html):
            if "/remote-jobs/" not in link and "remoteok.com" not in link:
                continue
            url = link if link.startswith("http") else f"https://remoteok.com{link}"
            jobs.append(
                JobRecord(
                    title=title,
                    company="Unknown",
                    location="Remote",
                    source=self.source,
                    url=url,
                    date_posted="",
                    remote_flag=True,
                    tags=["remote"],
                    description="RemoteOK HTML fallback listing",
                ).finalize()
            )
        return jobs
