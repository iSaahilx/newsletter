from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from intelligence.config import Settings, SourceCatalog
from intelligence.dashboard import render_dashboard
from intelligence.db import (
    connect,
    detect_trends,
    init_db,
    item_seen,
    recent_items,
    save_brief,
    save_intelligence_items,
    upsert_raw_items,
)
from intelligence.fetchers.markets import fetch_market_moves
from intelligence.fetchers.research import fetch_arxiv_categories, fetch_arxiv_topic, fetch_huggingface_papers
from intelligence.fetchers.rss import fetch_rss_sources
from intelligence.llm import IntelligenceLLM
from intelligence.models import Brief, IntelligenceItem, RawItem
from intelligence.progress import log, success
from intelligence.text import is_near_duplicate, normalize_title


async def run_daily(settings: Settings, sources: SourceCatalog) -> Brief:
    log("Starting daily intelligence run...")
    log(f"Database: {settings.database_path}")
    log(f"Output directory: {settings.output_dir}")
    conn = connect(settings.database_path)
    init_db(conn)

    fetched = await collect_items(settings, sources)
    log(f"Collected {len(fetched)} raw items before dedupe")
    fetched = _dedupe_raw(fetched)
    log(f"Kept {len(fetched)} raw items after dedupe")
    upsert_raw_items(conn, fetched)
    log("Saved raw items to database")

    fresh = [item for item in fetched if not item_seen(conn, item.url)]
    scoring_limit = min(settings.max_items_per_run, settings.scoring_item_limit)
    fresh = _prioritize_raw(fresh)[:scoring_limit]
    log(
        f"Found {len(fresh)} fresh high-priority items to score "
        f"(cap {scoring_limit}; fetched max {settings.max_items_per_run})"
    )
    llm = IntelligenceLLM(settings)
    scored = llm.score_items(fresh)
    important = [
        item for item in scored if item.importance_score >= settings.min_importance_score
    ]
    log(
        f"Kept {len(important)} items above importance threshold "
        f"{settings.min_importance_score}"
    )
    important = _dedupe_intelligence(important)
    log(f"Kept {len(important)} important items after event dedupe")
    important.sort(key=lambda item: item.importance_score, reverse=True)

    save_intelligence_items(conn, important)
    log("Saved scored intelligence items")
    trends = detect_trends(conn)
    log(f"Detected {len(trends)} emerging trends")
    items_for_brief = recent_items(conn, limit=settings.final_brief_item_limit)
    log(f"Loaded {len(items_for_brief)} stored items for final brief")
    markdown = llm.generate_brief(items_for_brief, trends)

    title = f"Today's Important Shifts - {datetime.now(timezone.utc).date().isoformat()}"
    save_brief(conn, title, markdown)
    output_path = write_output(settings.output_dir, markdown, "daily-brief")
    latest_path = settings.output_dir / "latest.md"
    latest_path.write_text(markdown, encoding="utf-8")
    log(f"Wrote Markdown brief: {output_path}")
    log(f"Updated latest brief: {latest_path}")
    dashboard_path = render_dashboard(settings.output_dir, items_for_brief, trends)
    log(f"Wrote dashboard: {dashboard_path}")
    success("Daily intelligence run complete")

    return Brief(
        generated_at=datetime.now(timezone.utc),
        title=title,
        markdown=f"{markdown}\n\n<!-- saved: {output_path.name} -->\n",
        items=items_for_brief,
        trends=trends,
    )


async def collect_items(settings: Settings, sources: SourceCatalog) -> list[RawItem]:
    log("Collecting RSS/news/research feeds and market moves...")
    rss_task = fetch_rss_sources(sources.rss_sources, per_source_limit=settings.rss_items_per_source)
    market_task = fetch_market_moves(
        sources.tickers,
        threshold_percent=settings.market_move_threshold_percent,
    )
    arxiv_task = fetch_arxiv_categories(limit_per_category=12)
    hf_task = fetch_huggingface_papers(limit=20)
    rss_items, market_items, arxiv_items, hf_items = await asyncio.gather(
        rss_task,
        market_task,
        arxiv_task,
        hf_task,
    )
    log(
        "Collection complete: "
        f"{len(rss_items)} RSS items, {len(market_items)} market items, "
        f"{len(arxiv_items)} arXiv items, {len(hf_items)} Hugging Face paper items"
    )
    return [*rss_items, *market_items, *arxiv_items, *hf_items]


async def run_research(settings: Settings, topic: str) -> Path:
    log(f"Starting research run for topic: {topic}")
    items = await fetch_arxiv_topic(topic, limit=16)
    llm = IntelligenceLLM(settings)
    markdown = llm.research_report(topic, items)
    path = write_output(settings.output_dir, markdown, f"research-{_slug(topic)}")
    success(f"Research run complete: {path}")
    return path


def write_output(output_dir: Path, markdown: str, prefix: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M%S")
    path = output_dir / f"{prefix}-{stamp}.md"
    path.write_text(markdown, encoding="utf-8")
    return path


def _dedupe_raw(items: list[RawItem]) -> list[RawItem]:
    kept: list[RawItem] = []
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    for item in sorted(items, key=lambda x: x.published_at, reverse=True):
        title_key = normalize_title(item.title)
        if item.url in seen_urls:
            continue
        if title_key in seen_titles:
            continue
        if any(is_near_duplicate(item.title, existing.title) for existing in kept[-80:]):
            continue
        seen_urls.add(item.url)
        seen_titles.add(title_key)
        kept.append(item)
    return kept


def _dedupe_intelligence(items: list[IntelligenceItem]) -> list[IntelligenceItem]:
    kept: list[IntelligenceItem] = []
    seen_events: set[str] = set()
    for item in items:
        event_key = normalize_title(item.canonical_event)
        if event_key in seen_events:
            continue
        if any(is_near_duplicate(item.canonical_event, existing.canonical_event) for existing in kept[-60:]):
            continue
        seen_events.add(event_key)
        kept.append(item)
    return kept


def _prioritize_raw(items: list[RawItem]) -> list[RawItem]:
    return sorted(items, key=_raw_priority_score, reverse=True)


def _raw_priority_score(item: RawItem) -> float:
    text = f"{item.title} {item.summary}".lower()
    score = 0.0
    category_boosts = {
        "research": 30,
        "ai_labs": 25,
        "deep_tech_learning": 24,
        "videos": 22,
        "science_and_tech": 20,
        "tools": 18,
        "big_tech": 16,
        "markets": 12,
        "business_and_markets": 10,
    }
    score += category_boosts.get(item.category, 0)
    for keyword, boost in {
        "agent": 12,
        "llm": 10,
        "reasoning": 10,
        "quantum": 12,
        "robot": 10,
        "infrastructure": 10,
        "gpu": 8,
        "nvidia": 10,
        "openai": 10,
        "anthropic": 10,
        "google research": 8,
        "breakthrough": 12,
        "paper": 8,
        "scaling law": 10,
        "security": 8,
        "backdoor": 10,
        "database": 6,
        "distributed": 6,
        "antibiotic": 8,
        "materials": 8,
    }.items():
        if keyword in text:
            score += boost
    summary_len = min(len(item.summary), 1200)
    score += summary_len / 300
    timestamp = item.published_at.timestamp() if item.published_at else 0
    return score + (timestamp / 10_000_000_000)


def _slug(value: str) -> str:
    return "-".join(part for part in value.lower().split() if part.isalnum())[:80] or "topic"
