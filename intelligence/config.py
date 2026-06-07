from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from intelligence.models import Source


ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseModel):
    openai_api_key: str | None = None
    openai_small_model: str = "gpt-4.1-nano"
    openai_large_model: str = "gpt-4.1-mini"
    database_path: Path = ROOT / "data" / "intelligence.sqlite3"
    output_dir: Path = ROOT / "output"
    sources_path: Path = ROOT / "sources.yaml"
    max_items_per_run: int = 180
    scoring_item_limit: int = 72
    final_brief_item_limit: int = 28
    rss_items_per_source: int = 20
    min_importance_score: int = 70
    market_move_threshold_percent: float = 3.0


class SourceCatalog(BaseModel):
    interests: dict[str, list[str]] = Field(default_factory=dict)
    tickers: list[str] = Field(default_factory=list)
    rss_sources: dict[str, list[Source]] = Field(default_factory=dict)


def load_settings() -> Settings:
    load_dotenv(ROOT / ".env")
    settings = Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_small_model=os.getenv("OPENAI_SMALL_MODEL", "gpt-4.1-nano"),
        openai_large_model=os.getenv("OPENAI_LARGE_MODEL", "gpt-4.1-mini"),
        database_path=Path(os.getenv("DATABASE_PATH", ROOT / "data" / "intelligence.sqlite3")),
        output_dir=Path(os.getenv("OUTPUT_DIR", ROOT / "output")),
        max_items_per_run=int(os.getenv("MAX_ITEMS_PER_RUN", "180")),
        scoring_item_limit=int(os.getenv("SCORING_ITEM_LIMIT", "72")),
        final_brief_item_limit=int(os.getenv("FINAL_BRIEF_ITEM_LIMIT", "28")),
        rss_items_per_source=int(os.getenv("RSS_ITEMS_PER_SOURCE", "20")),
        min_importance_score=int(os.getenv("MIN_IMPORTANCE_SCORE", "70")),
        market_move_threshold_percent=float(os.getenv("MARKET_MOVE_THRESHOLD_PERCENT", "3")),
    )
    if not settings.database_path.is_absolute():
        settings.database_path = ROOT / settings.database_path
    if not settings.output_dir.is_absolute():
        settings.output_dir = ROOT / settings.output_dir
    return settings


def load_sources(path: Path | None = None) -> SourceCatalog:
    source_path = path or ROOT / "sources.yaml"
    raw: dict[str, Any] = yaml.safe_load(source_path.read_text(encoding="utf-8"))
    return SourceCatalog.model_validate(raw)
