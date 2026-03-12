from __future__ import annotations

from difflib import SequenceMatcher
import re
from html import unescape

COMPANY_SUFFIXES = {
    "inc",
    "inc.",
    "llc",
    "ltd",
    "ltd.",
    "corp",
    "corp.",
    "co",
    "co.",
    "gmbh",
    "plc",
}


def text_contains_keywords(text: str, keywords: list[str]) -> list[str]:
    lowered = (text or "").lower()
    return [kw for kw in keywords if kw.lower() in lowered]


def clean_html(value: str) -> str:
    plain = re.sub(r"<[^>]+>", " ", value or "")
    plain = re.sub(r"\s+", " ", unescape(plain)).strip()
    return plain


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", (value or "").lower())).strip()


def normalize_company_name(value: str) -> str:
    parts = [
        token for token in normalize_text(value).split() if token and token not in COMPANY_SUFFIXES
    ]
    return " ".join(parts)


def title_token_key(value: str) -> str:
    return " ".join(sorted(normalize_text(value).split()))


def similarity_ratio(left: str, right: str) -> float:
    return SequenceMatcher(None, normalize_text(left), normalize_text(right)).ratio()


def token_similarity(left: str, right: str) -> float:
    left_tokens = set(normalize_text(left).split())
    right_tokens = set(normalize_text(right).split())
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def extract_links_from_html(html: str) -> list[tuple[str, str]]:
    links: list[tuple[str, str]] = []
    for href, title in re.findall(
        r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, flags=re.I | re.S
    ):
        clean_title = clean_html(title)
        if href and clean_title and len(clean_title) > 5:
            links.append((href, clean_title[:180]))
    return links
