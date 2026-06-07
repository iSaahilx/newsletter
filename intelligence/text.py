from __future__ import annotations

import re
from html import unescape
from difflib import SequenceMatcher

from bs4 import BeautifulSoup


def clean_html(value: str | None, max_chars: int = 1200) -> str:
    if not value:
        return ""
    soup = BeautifulSoup(value, "html.parser")
    text = soup.get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", unescape(text)).strip()
    return text[:max_chars]


def normalize_title(title: str) -> str:
    title = title.lower()
    title = re.sub(r"https?://\S+", "", title)
    title = re.sub(r"[^a-z0-9\s]", " ", title)
    title = re.sub(r"\b(the|a|an|new|latest|report|study|says)\b", " ", title)
    return re.sub(r"\s+", " ", title).strip()


def is_near_duplicate(a: str, b: str, threshold: float = 0.88) -> bool:
    return SequenceMatcher(None, normalize_title(a), normalize_title(b)).ratio() >= threshold
