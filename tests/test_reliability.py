import asyncio
import httpx

from job_hunter.config import Settings
from job_hunter.scrapers.base import Scraper, run_scraper_safe


class BrokenScraper(Scraper):
    source = "broken"

    async def scrape(self, client: httpx.AsyncClient, settings: Settings):
        raise RuntimeError("boom")


def test_degraded_mode_scraper_failure_isolated():
    async def _run():
        async with httpx.AsyncClient() as client:
            return await run_scraper_safe(BrokenScraper(), client, Settings())

    source, jobs, err = asyncio.run(_run())
    assert source == "broken"
    assert jobs == []
    assert "boom" in err
