from __future__ import annotations

import xml.etree.ElementTree as ET
from urllib.parse import urlencode

import httpx

from ..config import Settings
from ..models import JobRecord
from ..utils import clean_html
from .base import Scraper, fetch_text_with_retry


class IndeedScraper(Scraper):
    source = "indeed"
    base_url = "https://ca.indeed.com/rss"

    async def scrape(self, client: httpx.AsyncClient, settings: Settings) -> list[JobRecord]:
        jobs: list[JobRecord] = []
        for keyword in settings.include_keywords:
            url = f"{self.base_url}?{urlencode({'q': keyword, 'l': 'Canada', 'sort': 'date'})}"
            xml_text = await fetch_text_with_retry(client, url, settings)
            root = ET.fromstring(xml_text)
            for item in root.findall(".//item"):
                job = JobRecord(
                    title=item.findtext("title") or "",
                    company=item.findtext("source") or "",
                    location=item.findtext("location") or "Canada",
                    source=self.source,
                    url=item.findtext("link") or "",
                    date_posted=item.findtext("pubDate") or "",
                    remote_flag="remote" in (item.findtext("title") or "").lower(),
                    tags=[keyword],
                    description=clean_html(item.findtext("description") or ""),
                ).finalize()
                if job.url:
                    jobs.append(job)
        return jobs
