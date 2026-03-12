from __future__ import annotations

import re
from html import unescape


def text_contains_keywords(text: str, keywords: list[str]) -> list[str]:
    lowered = text.lower()
    return [kw for kw in keywords if kw.lower() in lowered]


def clean_html(value: str) -> str:
    plain = re.sub(r"<[^>]+>", " ", value or "")
    plain = re.sub(r"\s+", " ", unescape(plain)).strip()
    return plain
