from __future__ import annotations

import httpx

from ..config import Settings
from ..models import JobRecord
from ..utils import clean_html
from .base import Scraper, fetch_json_with_retry


class HackerNewsScraper(Scraper):
    source = "hackernews"
    search_url = "https://hn.algolia.com/api/v1/search"

    async def scrape(self, client: httpx.AsyncClient, settings: Settings) -> list[JobRecord]:
        result = await fetch_json_with_retry(
            client,
            self.search_url,
            settings,
            params={"query": "Ask HN: Who is hiring?", "tags": "story,ask_hn", "hitsPerPage": 1},
        )
        hits = result.get("hits", []) if isinstance(result, dict) else []
        if not hits:
            return []
        thread_id = hits[0].get("objectID")

        jobs: list[JobRecord] = []
        for keyword in settings.include_keywords:
            data = await fetch_json_with_retry(
                client,
                self.search_url,
                settings,
                params={"query": keyword, "tags": f"comment,story_{thread_id}", "hitsPerPage": 20},
            )
            for hit in data.get("hits", []) if isinstance(data, dict) else []:
                text = clean_html(hit.get("comment_text") or hit.get("story_text") or "")
                line = text.split("\n", maxsplit=1)[0][:120] if text else f"HN Hiring - {keyword}"
                obj_id = hit.get("objectID")
                job = JobRecord(
                    title=line,
                    company="Unknown",
                    location="Remote / Various",
                    source=self.source,
                    url=f"https://news.ycombinator.com/item?id={obj_id}",
                    date_posted=hit.get("created_at") or "",
                    remote_flag="remote" in text.lower(),
                    tags=[keyword],
                    description=text,
                ).finalize()
                jobs.append(job)
        return jobs
