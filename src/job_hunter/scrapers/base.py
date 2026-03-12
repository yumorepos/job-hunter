from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
import logging
from typing import Any

import httpx

from ..config import Settings
from ..models import JobRecord


class Scraper(ABC):
    source: str

    @abstractmethod
    async def scrape(self, client: httpx.AsyncClient, settings: Settings) -> list[JobRecord]:
        raise NotImplementedError


async def fetch_json_with_retry(
    client: httpx.AsyncClient,
    url: str,
    settings: Settings,
    **kwargs: Any,
) -> Any:
    last_error: Exception | None = None
    for attempt in range(settings.max_retries + 1):
        try:
            resp = await client.get(url, timeout=settings.request_timeout, **kwargs)
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            last_error = exc
            if attempt < settings.max_retries:
                await asyncio.sleep(settings.backoff_seconds * (attempt + 1))
    raise RuntimeError(f"request failed for {url}: {last_error}")


async def fetch_text_with_retry(
    client: httpx.AsyncClient,
    url: str,
    settings: Settings,
    **kwargs: Any,
) -> str:
    last_error: Exception | None = None
    for attempt in range(settings.max_retries + 1):
        try:
            resp = await client.get(url, timeout=settings.request_timeout, **kwargs)
            resp.raise_for_status()
            return resp.text
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt < settings.max_retries:
                await asyncio.sleep(settings.backoff_seconds * (attempt + 1))
    raise RuntimeError(f"request failed for {url}: {last_error}")


async def run_scraper_safe(
    scraper: Scraper, client: httpx.AsyncClient, settings: Settings
) -> tuple[str, list[JobRecord], str | None]:
    try:
        return scraper.source, await scraper.scrape(client, settings), None
    except Exception as exc:  # noqa: BLE001
        logging.getLogger(__name__).warning(
            "scraper_failed", extra={"source": scraper.source, "error": str(exc)}
        )
        return scraper.source, [], str(exc)
