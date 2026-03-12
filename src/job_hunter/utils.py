from __future__ import annotations

from difflib import SequenceMatcher
import re
from html import unescape


def text_contains_keywords(text: str, keywords: list[str]) -> list[str]:
    lowered = (text or "").lower()
    return [kw for kw in keywords if kw.lower() in lowered]


def clean_html(value: str) -> str:
    plain = re.sub(r"<[^>]+>", " ", value or "")
    plain = re.sub(r"\s+", " ", unescape(plain)).strip()
    return plain


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", (value or "").lower())).strip()


def similarity_ratio(left: str, right: str) -> float:
    return SequenceMatcher(None, normalize_text(left), normalize_text(right)).ratio()


def extract_links_from_html(html: str) -> list[tuple[str, str]]:
    links: list[tuple[str, str]] = []
    for href, title in re.findall(
        r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, flags=re.I | re.S
    ):
        clean_title = clean_html(title)
        if href and clean_title and len(clean_title) > 5:
            links.append((href, clean_title[:180]))
    return links
