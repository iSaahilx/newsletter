from __future__ import annotations

from datetime import datetime, timezone
from typing import Awaitable
from urllib.parse import quote_plus

import feedparser
import httpx
from bs4 import BeautifulSoup

from intelligence.models import ItemKind, RawItem
from intelligence.progress import log, warn
from intelligence.text import clean_html


ARXIV_CATEGORIES = {
    "cs.AI": "Artificial Intelligence",
    "cs.LG": "Machine Learning",
    "cs.CL": "Computation and Language",
    "cs.RO": "Robotics",
    "quant-ph": "Quantum Physics",
}


async def fetch_arxiv_categories(limit_per_category: int = 12) -> list[RawItem]:
    log(f"Fetching arXiv API categories ({len(ARXIV_CATEGORIES)} categories)...")
    async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
        results = await asyncio_gather_limited(
            [
                _fetch_arxiv_category(client, category, label, limit_per_category)
                for category, label in ARXIV_CATEGORIES.items()
            ],
            limit=3,
        )
    items = [item for group in results for item in group]
    log(f"Fetched {len(items)} arXiv API items")
    return items


async def fetch_huggingface_papers(limit: int = 20) -> list[RawItem]:
    log("Fetching Hugging Face Papers page...")
    try:
        async with httpx.AsyncClient(
            timeout=20.0,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 personal-intelligence-system/0.1"},
        ) as client:
            response = await client.get("https://huggingface.co/papers")
            response.raise_for_status()
    except Exception:
        warn("Hugging Face Papers page fetch failed")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    items: list[RawItem] = []
    seen_urls: set[str] = set()
    for link in soup.find_all("a", href=True):
        href = link["href"]
        title = clean_html(link.get_text(" ", strip=True), max_chars=300)
        if not href.startswith("/papers/") or len(title) < 20:
            continue
        url = f"https://huggingface.co{href}"
        if url in seen_urls:
            continue
        seen_urls.add(url)
        items.append(
            RawItem(
                title=title,
                url=url,
                source="Hugging Face Papers",
                category="research",
                kind=ItemKind.PAPER,
                summary="Trending paper surfaced on Hugging Face Papers.",
                published_at=datetime.now(timezone.utc),
                metadata={"fetcher": "huggingface_papers_page"},
            )
        )
        if len(items) >= limit:
            break
    log(f"Fetched {len(items)} Hugging Face paper items")
    return items


async def fetch_arxiv_topic(topic: str, limit: int = 12) -> list[RawItem]:
    log(f"Fetching arXiv papers for research topic: {topic}")
    query = quote_plus(f'all:"{topic}"')
    url = (
        "https://export.arxiv.org/api/query"
        f"?search_query={query}&start=0&max_results={limit}&sortBy=submittedDate&sortOrder=descending"
    )
    try:
        async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
    except Exception:
        warn(f"arXiv fetch failed for topic: {topic}")
        return []

    parsed = feedparser.parse(response.text)
    items: list[RawItem] = []
    for entry in parsed.entries[:limit]:
        items.append(
            RawItem(
                title=clean_html(entry.get("title"), max_chars=300),
                url=entry.get("link"),
                source="arXiv",
                category="research",
                kind=ItemKind.PAPER,
                summary=clean_html(entry.get("summary"), max_chars=1800),
                authors=[author.get("name") for author in entry.get("authors", []) if author.get("name")],
                published_at=_entry_time(entry),
                metadata={"topic": topic},
            )
        )
    valid_items = [item for item in items if item.title and item.url]
    log(f"Fetched {len(valid_items)} arXiv papers for: {topic}")
    return valid_items


async def _fetch_arxiv_category(
    client: httpx.AsyncClient,
    category: str,
    label: str,
    limit: int,
) -> list[RawItem]:
    url = (
        "https://export.arxiv.org/api/query"
        f"?search_query=cat:{quote_plus(category)}&start=0&max_results={limit}"
        "&sortBy=submittedDate&sortOrder=descending"
    )
    try:
        response = await client.get(url)
        response.raise_for_status()
    except Exception:
        warn(f"arXiv category fetch failed: {category}")
        return []

    parsed = feedparser.parse(response.text)
    items: list[RawItem] = []
    for entry in parsed.entries[:limit]:
        items.append(
            RawItem(
                title=clean_html(entry.get("title"), max_chars=300),
                url=entry.get("link"),
                source=f"arXiv {label}",
                category="research",
                kind=ItemKind.PAPER,
                summary=clean_html(entry.get("summary"), max_chars=1800),
                authors=[author.get("name") for author in entry.get("authors", []) if author.get("name")],
                published_at=_entry_time(entry),
                metadata={"arxiv_category": category},
            )
        )
    return [item for item in items if item.title and item.url]


async def asyncio_gather_limited(
    coros: list[Awaitable[list[RawItem]]],
    limit: int,
) -> list[list[RawItem]]:
    import asyncio

    semaphore = asyncio.Semaphore(limit)

    async def run(coro: Awaitable[list[RawItem]]) -> list[RawItem]:
        async with semaphore:
            return await coro

    return await asyncio.gather(*(run(coro) for coro in coros))


def _entry_time(entry: object) -> datetime:
    value = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if not value:
        return datetime.now(timezone.utc)
    return datetime(*value[:6], tzinfo=timezone.utc)
