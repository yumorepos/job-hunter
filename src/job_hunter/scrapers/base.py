from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
import logging
import random
from typing import Any

import httpx

from ..config import Settings
from ..models import JobRecord

LOGGER = logging.getLogger(__name__)
USER_AGENTS = [
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3) AppleWebKit/605.1.15 Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
]


class Scraper(ABC):
    source: str

    @abstractmethod
    async def scrape(self, client: httpx.AsyncClient, settings: Settings) -> list[JobRecord]:
        raise NotImplementedError


async def _request_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    settings: Settings,
    **kwargs: Any,
) -> httpx.Response:
    last_error: Exception | None = None
    headers = dict(kwargs.pop("headers", {}))
    for attempt in range(settings.max_retries + 1):
        try:
            headers["User-Agent"] = random.choice(USER_AGENTS)
            resp = await client.request(
                method,
                url,
                timeout=settings.request_timeout,
                headers=headers,
                **kwargs,
            )
            resp.raise_for_status()
            return resp
        except httpx.HTTPError as exc:
            last_error = exc
            LOGGER.info(
                "scraper_retry",
                extra={"url": url, "attempt": attempt + 1, "error": str(exc)},
            )
            if attempt < settings.max_retries:
                await asyncio.sleep(settings.backoff_seconds * (2**attempt))
    raise RuntimeError(f"request failed for {url}: {last_error}")


async def fetch_json_with_retry(
    client: httpx.AsyncClient,
    url: str,
    settings: Settings,
    **kwargs: Any,
) -> Any:
    response = await _request_with_retry(client, "GET", url, settings, **kwargs)
    try:
        return response.json()
    except ValueError as exc:  # pragma: no cover - edge cases from live sources
        raise RuntimeError(f"invalid json for {url}: {exc}") from exc


async def fetch_text_with_retry(
    client: httpx.AsyncClient,
    url: str,
    settings: Settings,
    **kwargs: Any,
) -> str:
    response = await _request_with_retry(client, "GET", url, settings, **kwargs)
    return response.text


async def run_scraper_safe(
    scraper: Scraper, client: httpx.AsyncClient, settings: Settings
) -> tuple[str, list[JobRecord], str | None]:
    try:
        jobs = await scraper.scrape(client, settings)
        LOGGER.info("scraper_success", extra={"source": scraper.source, "jobs": len(jobs)})
        return scraper.source, jobs, None
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("scraper_failed", extra={"source": scraper.source, "error": str(exc)})
        return scraper.source, [], str(exc)
