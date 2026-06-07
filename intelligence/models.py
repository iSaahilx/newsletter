from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, Field, HttpUrl


class ItemKind(StrEnum):
    NEWS = "news"
    PAPER = "paper"
    MARKET = "market"
    TOOL = "tool"
    COMPANY = "company"
    UNIVERSITY = "university"
    VIDEO = "video"
    EXPLAINER = "explainer"


class RawItem(BaseModel):
    title: str
    url: str
    source: str
    category: str
    kind: ItemKind = ItemKind.NEWS
    summary: str = ""
    authors: list[str] = Field(default_factory=list)
    published_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, str | int | float | bool] = Field(default_factory=dict)


class IntelligenceItem(RawItem):
    canonical_event: str
    analysis_type: str = "news"
    story_hook: str = ""
    what_happened: str
    why_it_matters: str
    how_it_works: str
    deep_explanation: str = ""
    learning_value: str = ""
    what_to_watch: str
    importance_score: int = Field(ge=0, le=100)
    novelty_score: int = Field(ge=0, le=100)
    technical_score: int = Field(ge=0, le=100)
    business_score: int = Field(ge=0, le=100)
    long_term_score: int = Field(ge=0, le=100)
    entities: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    reasoning: str = ""


class Trend(BaseModel):
    topic: str
    recent_count: int
    baseline_count: int
    lift: float
    explanation: str


class Brief(BaseModel):
    generated_at: datetime
    title: str
    markdown: str
    items: list[IntelligenceItem]
    trends: list[Trend]


class Source(BaseModel):
    name: str
    url: HttpUrl
