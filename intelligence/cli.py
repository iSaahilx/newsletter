from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from rich.console import Console

from intelligence.config import load_settings, load_sources
from intelligence.dashboard import render_dashboard
from intelligence.db import (
    connect,
    detect_trends,
    init_db,
    items_for_entity,
    recent_items,
    recent_raw_items,
    save_intelligence_items,
)
from intelligence.llm import IntelligenceLLM
from intelligence.pipeline import run_daily, run_research
from intelligence.progress import log, success


app = typer.Typer(help="Personal AI/tech/science/markets intelligence system.")
console = Console()


@app.command()
def init() -> None:
    """Create the local database and output folder."""

    settings = load_settings()
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    conn = connect(settings.database_path)
    init_db(conn)
    console.print(f"Initialized database at [bold]{settings.database_path}[/bold]")


@app.command()
def daily() -> None:
    """Fetch sources, score important events, detect trends, and write the daily brief."""

    settings = load_settings()
    sources = load_sources(settings.sources_path)
    brief = asyncio.run(run_daily(settings, sources))
    console.print(f"[bold green]Generated:[/bold green] {brief.title}")
    console.print(f"Saved latest brief to [bold]{settings.output_dir / 'latest.md'}[/bold]")


@app.command()
def research(topic: str = typer.Argument(..., help="Topic to research, e.g. 'Mixture of Experts'")) -> None:
    """Generate a research primer for a topic using recent papers plus OpenAI synthesis."""

    settings = load_settings()
    path = asyncio.run(run_research(settings, topic))
    console.print(f"[bold green]Research report saved:[/bold green] {path}")


@app.command()
def top(limit: int = 10) -> None:
    """Show the highest-scored stored intelligence items."""

    settings = load_settings()
    conn = connect(settings.database_path)
    init_db(conn)
    for item in recent_items(conn, limit=limit):
        console.print(f"[bold]{item.importance_score}/100[/bold] {item.title}")
        console.print(f"{item.source} - {item.url}")


@app.command()
def entity(name: str, limit: int = 10) -> None:
    """Show what the system has recently learned about an entity."""

    settings = load_settings()
    conn = connect(settings.database_path)
    init_db(conn)
    matches = items_for_entity(conn, name, limit=limit)
    if not matches:
        console.print(f"No stored intelligence found for entity: [bold]{name}[/bold]")
        return
    for item in matches:
        console.print(f"[bold]{item.title}[/bold]")
        console.print(f"{item.what_happened}")
        console.print(f"{item.source} - {item.url}\n")


@app.command()
def dashboard(limit: int = 80) -> None:
    """Regenerate the local HTML dashboard from stored intelligence items."""

    settings = load_settings()
    conn = connect(settings.database_path)
    init_db(conn)
    log(f"Loading up to {limit} stored items for dashboard...")
    items = recent_items(conn, limit=limit)
    trends = detect_trends(conn)
    log(f"Rendering dashboard from {len(items)} items and {len(trends)} trends...")
    path = render_dashboard(settings.output_dir, items, trends)
    success(f"Dashboard saved: {path}")


@app.command()
def reanalyze(limit: int = 120) -> None:
    """Rescore recent raw items with the current prompts and regenerate the dashboard."""

    settings = load_settings()
    conn = connect(settings.database_path)
    init_db(conn)
    log(f"Loading up to {limit} raw items for reanalysis...")
    raw_items = recent_raw_items(conn, limit=limit)
    log(f"Loaded {len(raw_items)} raw items")
    scored = IntelligenceLLM(settings).score_items(raw_items)
    important = [item for item in scored if item.importance_score >= settings.min_importance_score]
    log(
        f"Keeping {len(important)} items above importance threshold "
        f"{settings.min_importance_score}"
    )
    save_intelligence_items(conn, important)
    log("Saved reanalyzed intelligence items")
    path = render_dashboard(settings.output_dir, recent_items(conn, limit=80), detect_trends(conn))
    success(f"Reanalyzed {len(important)} items")
    success(f"Dashboard saved: {path}")


@app.command()
def show_latest() -> None:
    """Print the latest generated Markdown brief."""

    settings = load_settings()
    path = Path(settings.output_dir) / "latest.md"
    if not path.exists():
        raise typer.BadParameter("No latest brief exists yet. Run `intel daily` first.")
    console.print(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    app()
