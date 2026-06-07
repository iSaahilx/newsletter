from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser
import httpx

from intelligence.models import ItemKind, RawItem, Source
from intelligence.progress import log, warn
from intelligence.text import clean_html


KIND_BY_CATEGORY = {
    "research": ItemKind.PAPER,
    "tools": ItemKind.TOOL,
    "big_tech": ItemKind.COMPANY,
    "universities": ItemKind.UNIVERSITY,
    "videos": ItemKind.VIDEO,
    "deep_tech_learning": ItemKind.EXPLAINER,
}


async def fetch_rss_sources(
    grouped_sources: dict[str, list[Source]],
    per_source_limit: int = 10,
    timeout_seconds: float = 12.0,
) -> list[RawItem]:
    all_sources = [
        (category, source)
        for category, sources in grouped_sources.items()
        for source in sources
    ]
    total_sources = sum(len(sources) for sources in grouped_sources.values())
    log(f"Fetching RSS feeds from {total_sources} sources...")
    async with httpx.AsyncClient(
        timeout=timeout_seconds,
        follow_redirects=True,
        headers={"User-Agent": "personal-intelligence-system/0.1"},
    ) as client:
        for category, sources in grouped_sources.items():
            log(f"Queueing category '{category}' ({len(sources)} sources)...")
        semaphore = asyncio.Semaphore(12)

        async def fetch_with_limit(category: str, source: Source) -> list[RawItem]:
            async with semaphore:
                return await _fetch_single_source(client, category, source, per_source_limit)

        results = await asyncio.gather(
            *(fetch_with_limit(category, source) for category, source in all_sources)
        )
    items = [item for group in results for item in group]
    log(f"Finished RSS fetching: {len(items)} raw items")
    return items


async def _fetch_single_source(
    client: httpx.AsyncClient,
    category: str,
    source: Source,
    per_source_limit: int,
) -> list[RawItem]:
    log(f"  -> {source.name}")
    try:
        response = await client.get(str(source.url))
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        warn(f"  !! skipped {source.name} (HTTP {exc.response.status_code})")
        return []
    except Exception as exc:
        warn(f"  !! skipped {source.name} ({type(exc).__name__}: {exc})")
        return []

    parsed = feedparser.parse(response.text)
    items: list[RawItem] = []
    for entry in parsed.entries[:per_source_limit]:
        url = entry.get("link")
        title = clean_html(entry.get("title"), max_chars=300)
        if not url or not title:
            continue
        items.append(
            RawItem(
                title=title,
                url=url,
                source=source.name,
                category=category,
                kind=KIND_BY_CATEGORY.get(category, ItemKind.NEWS),
                summary=clean_html(entry.get("summary") or entry.get("description"), max_chars=1600),
                authors=_authors(entry),
                published_at=_published_at(entry),
                metadata={"feed_url": str(source.url)},
            )
        )
    log(f"  <- {source.name}: {len(items)} items")
    return items


def _authors(entry: object) -> list[str]:
    authors = []
    for author in getattr(entry, "authors", []) or []:
        name = author.get("name") if isinstance(author, dict) else None
        if name:
            authors.append(name)
    direct_author = getattr(entry, "author", None)
    if direct_author and direct_author not in authors:
        authors.append(direct_author)
    return authors


def _published_at(entry: object) -> datetime:
    for key in ("published", "updated", "created"):
        value = getattr(entry, key, None)
        if not value:
            continue
        try:
            dt = parsedate_to_datetime(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            continue
    return datetime.now(timezone.utc)
