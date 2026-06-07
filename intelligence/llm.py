from __future__ import annotations

import json
from typing import Any

from openai import OpenAI, OpenAIError
from pydantic import ValidationError

from intelligence.config import Settings
from intelligence.models import IntelligenceItem, RawItem, Trend
from intelligence.progress import log, success, warn


SYSTEM_PROMPT = """You are a personal intelligence analyst.
Your job is to filter noisy global AI, technology, science, startup, and market information.
Prioritize frontier AI, agentic AI, AI infrastructure, semiconductors, quantum computing,
robotics, energy, climate tech, leading labs, universities, startups, market-moving events,
engineering stories, high-quality explainers, and curiosity-driven science.
Do not force every item into the same four-line template. Research papers, engineering
posts, and technical breakthroughs need a proper mechanism explanation. Market events need
drivers and second-order effects. Videos and explainers need the core idea and why it is worth learning.
Be skeptical. Ignore routine marketing, minor launches, shallow opinion pieces, and duplicate news.
"""


def has_openai(settings: Settings) -> bool:
    return bool(settings.openai_api_key)


class IntelligenceLLM:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None

    def score_items(self, raw_items: list[RawItem]) -> list[IntelligenceItem]:
        if not self.client:
            warn("OPENAI_API_KEY not set; using heuristic scoring")
            return [_heuristic_item(item) for item in raw_items]

        scored: list[IntelligenceItem] = []
        chunks = _chunks(raw_items, 12)
        log(
            f"Scoring {len(raw_items)} items with {self.settings.openai_small_model} "
            f"({len(chunks)} chunks)..."
        )
        for index, chunk in enumerate(chunks, start=1):
            log(f"  -> scoring chunk {index}/{len(chunks)} ({len(chunk)} items)")
            payload = [
                {
                    "title": item.title,
                    "url": item.url,
                    "source": item.source,
                    "category": item.category,
                    "kind": item.kind.value,
                    "summary": item.summary,
                    "published_at": item.published_at.isoformat(),
                    "metadata": item.metadata,
                }
                for item in chunk
            ]
            try:
                response = self.client.chat.completions.create(
                    model=self.settings.openai_small_model,
                    temperature=0.1,
                    response_format={"type": "json_object"},
                    max_completion_tokens=7000,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": (
                                "Score these candidate events. Return JSON with key 'items', an array "
                                "matching the input order. Each item must include canonical_event, "
                                "analysis_type, story_hook, what_happened, why_it_matters, "
                                "how_it_works, deep_explanation, learning_value, what_to_watch, "
                                "importance_score, novelty_score, technical_score, business_score, "
                                "long_term_score, entities, topics, reasoning. Scores are 0-100. "
                                "analysis_type must be one of: research_paper, technical_breakthrough, "
                                "tool_or_framework, engineering_story, market_move, company_strategy, "
                                "learning_video, science_explainer, general_news. "
                                "For papers and technical breakthroughs, deep_explanation should be "
                                "5-8 sentences, abstract-like, and explain the mechanism clearly. "
                                "For other items, deep_explanation can be 2-5 sentences. "
                                "learning_value explains what the reader will understand after reading. "
                                "Keep short fields concise but do not make how_it_works artificially one line.\n\n"
                                f"{json.dumps(payload, ensure_ascii=False)}"
                            ),
                        },
                    ],
                )
            except OpenAIError as exc:
                warn(f"  !! scoring chunk {index}/{len(chunks)} failed ({exc}); using heuristic fallback")
                scored.extend(_heuristic_item(item) for item in chunk)
                continue
            content = response.choices[0].message.content or "{}"
            try:
                decoded = json.loads(content)
                scored_payload = decoded.get("items", [])
            except json.JSONDecodeError:
                scored_payload = []

            for raw, data in zip(chunk, scored_payload, strict=False):
                try:
                    scored.append(_merge_scored(raw, data))
                except (ValidationError, TypeError, ValueError):
                    warn(f"  !! model response invalid for '{raw.title[:80]}'; using heuristic fallback")
                    scored.append(_heuristic_item(raw))
            log(f"  <- finished chunk {index}/{len(chunks)}")
        success(f"Scored {len(scored)} items")
        return scored

    def generate_brief(self, items: list[IntelligenceItem], trends: list[Trend]) -> str:
        if not self.client:
            warn("OPENAI_API_KEY not set; generating fallback Markdown brief")
            return _fallback_brief(items, trends)

        log(
            f"Generating final brief with {self.settings.openai_large_model} "
            f"from {len(items)} items and {len(trends)} trends..."
        )
        brief_items = items[: self.settings.final_brief_item_limit]
        payload = {
            "items": [_brief_item_payload(item) for item in brief_items],
            "trends": [trend.model_dump(mode="json") for trend in trends],
        }
        try:
            response = self.client.chat.completions.create(
                model=self.settings.openai_large_model,
                temperature=0.2,
                max_completion_tokens=5000,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            "Create a personal intelligence dashboard brief in Markdown. It is not only "
                            "daily news; include older-but-important learning items if they are high value. "
                            "Format:\n"
                            "# Important Tech, Science, and AI Signals\n"
                            "## Must Know Today\n"
                            "## Research Papers and Breakthroughs\n## AI and Infrastructure\n"
                            "## Tools and Engineering\n## Science, Quantum, and Curiosity\n"
                            "## Markets and Company Strategy\n## Videos Worth Learning From\n"
                            "## Emerging Trends\n## Deep Dive Suggestions\n\n"
                            "Do not force every item into the same labels. Use the item analysis_type. "
                            "For research_paper and technical_breakthrough, include a compact summary plus "
                            "an 'Expanded how it works' paragraph that reads like a clear abstract. "
                            "For learning_video or science_explainer, explain the story and the concept. "
                            "For market_move/company_strategy, explain likely drivers and what changes next. "
                            "Keep the visible summary scannable, but preserve substance. "
                            "Use only supplied items and trends.\n\n"
                            f"{json.dumps(payload, ensure_ascii=False)}"
                        ),
                    },
                ],
            )
        except OpenAIError as exc:
            warn(f"Final brief generation failed ({exc}); writing fallback brief instead")
            return _fallback_brief(items, trends)
        success("Generated final Markdown brief")
        return response.choices[0].message.content or _fallback_brief(items, trends)

    def research_report(self, topic: str, items: list[RawItem]) -> str:
        if not self.client:
            warn("OPENAI_API_KEY not set; generating fallback research report")
            return _fallback_research(topic, items)

        log(
            f"Generating research report for '{topic}' with {self.settings.openai_large_model} "
            f"from {len(items)} sources..."
        )
        payload = [item.model_dump(mode="json") for item in items]
        response = self.client.chat.completions.create(
            model=self.settings.openai_large_model,
            temperature=0.2,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Create a deep research primer on '{topic}' using these sources. "
                        "Sections: What it is, How it works, Key papers or milestones, "
                        "Who is using it, Why it matters, Limitations, Future outlook, "
                        "Best sources to read next. Keep it educational and practical.\n\n"
                        f"{json.dumps(payload, ensure_ascii=False)}"
                    ),
                },
            ],
        )
        success(f"Generated research report for '{topic}'")
        return response.choices[0].message.content or _fallback_research(topic, items)


def _merge_scored(raw: RawItem, data: dict[str, Any]) -> IntelligenceItem:
    return IntelligenceItem(
        **raw.model_dump(),
        canonical_event=str(data.get("canonical_event") or raw.title),
        analysis_type=str(data.get("analysis_type") or _analysis_type(raw)),
        story_hook=str(data.get("story_hook") or ""),
        what_happened=str(data.get("what_happened") or raw.summary or raw.title),
        why_it_matters=str(data.get("why_it_matters") or "Potentially relevant to tracked interests."),
        how_it_works=str(data.get("how_it_works") or "See source for technical details."),
        deep_explanation=str(data.get("deep_explanation") or ""),
        learning_value=str(data.get("learning_value") or ""),
        what_to_watch=str(data.get("what_to_watch") or "Follow related announcements and adoption."),
        importance_score=_score(data.get("importance_score"), 50),
        novelty_score=_score(data.get("novelty_score"), 50),
        technical_score=_score(data.get("technical_score"), 50),
        business_score=_score(data.get("business_score"), 50),
        long_term_score=_score(data.get("long_term_score"), 50),
        entities=[str(x) for x in data.get("entities", [])][:10],
        topics=[str(x).lower() for x in data.get("topics", [])][:10],
        reasoning=str(data.get("reasoning") or ""),
    )


def _brief_item_payload(item: IntelligenceItem) -> dict[str, Any]:
    return {
        "title": item.title,
        "url": item.url,
        "source": item.source,
        "category": item.category,
        "analysis_type": item.analysis_type,
        "importance_score": item.importance_score,
        "technical_score": item.technical_score,
        "business_score": item.business_score,
        "canonical_event": _limit_text(item.canonical_event, 220),
        "story_hook": _limit_text(item.story_hook, 220),
        "what_happened": _limit_text(item.what_happened, 420),
        "why_it_matters": _limit_text(item.why_it_matters, 420),
        "how_it_works": _limit_text(item.how_it_works, 520),
        "deep_explanation": _limit_text(item.deep_explanation, 900),
        "learning_value": _limit_text(item.learning_value, 320),
        "what_to_watch": _limit_text(item.what_to_watch, 260),
        "entities": item.entities[:8],
        "topics": item.topics[:8],
    }


def _limit_text(value: str, max_chars: int) -> str:
    value = " ".join((value or "").split())
    if len(value) <= max_chars:
        return value
    return value[: max_chars - 3].rstrip() + "..."


def _heuristic_item(raw: RawItem) -> IntelligenceItem:
    text = f"{raw.title} {raw.summary}".lower()
    score = 45
    for keyword, boost in {
        "openai": 15,
        "anthropic": 15,
        "deepmind": 12,
        "nvidia": 12,
        "agent": 10,
        "llm": 10,
        "quantum": 10,
        "robot": 8,
        "breakthrough": 12,
        "funding": 8,
        "acquisition": 8,
        "benchmark": 6,
    }.items():
        if keyword in text:
            score += boost
    score = min(score, 95)
    topics = [word for word in ["ai", "agents", "llm", "quantum", "robotics", "markets"] if word in text]
    return IntelligenceItem(
        **raw.model_dump(),
        canonical_event=raw.title,
        analysis_type=_analysis_type(raw),
        story_hook=_story_hook(raw),
        what_happened=raw.summary or raw.title,
        why_it_matters="This matched your tracked interests and may signal a relevant technical or market shift.",
        how_it_works=_heuristic_how(raw),
        deep_explanation=_heuristic_deep(raw),
        learning_value="Useful as a learning lead; the model-enhanced run will turn this into a clearer lesson.",
        what_to_watch="Watch follow-up coverage, adoption by major labs or companies, and benchmark evidence.",
        importance_score=score,
        novelty_score=min(score, 80),
        technical_score=score if raw.category in {"research", "tools", "ai_labs"} else 50,
        business_score=score if raw.category in {"business_and_markets", "markets", "big_tech"} else 45,
        long_term_score=min(score + 5, 95),
        entities=[],
        topics=topics or [raw.category],
        reasoning="Heuristic score because OPENAI_API_KEY was not configured.",
    )


def _score(value: Any, default: int) -> int:
    try:
        return max(0, min(100, int(value)))
    except Exception:
        return default


def _chunks(items: list[RawItem], size: int) -> list[list[RawItem]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def _analysis_type(raw: RawItem) -> str:
    text = f"{raw.title} {raw.summary}".lower()
    if raw.kind.value == "paper" or raw.category == "research":
        return "research_paper"
    if raw.kind.value == "video" or raw.category == "videos":
        return "learning_video"
    if raw.kind.value == "market" or raw.category == "markets":
        return "market_move"
    if raw.kind.value == "tool" or raw.category == "tools":
        return "tool_or_framework"
    if raw.category in {"deep_tech_learning", "science_and_tech"}:
        if any(word in text for word in ["quantum", "black hole", "particle", "virus", "antibiotic"]):
            return "science_explainer"
        return "technical_breakthrough"
    if raw.category in {"big_tech", "business_and_markets"}:
        return "company_strategy"
    return "general_news"


def _story_hook(raw: RawItem) -> str:
    if raw.kind.value == "video":
        return "A learning video worth saving for a deeper watch."
    if raw.category == "research":
        return "A research lead that may become important beyond the paper itself."
    if raw.category == "deep_tech_learning":
        return "An evergreen idea or engineering story worth understanding."
    return ""


def _heuristic_how(raw: RawItem) -> str:
    if raw.category == "research":
        return (
            "The source describes a proposed method or result; use the expanded section and original "
            "paper to inspect assumptions, model design, evaluation setup, and failure cases."
        )
    if raw.kind.value == "video":
        return "The video likely teaches the concept through a narrative, experiment, or historical case."
    return "Open the source for details; add OPENAI_API_KEY for a mechanism-level explanation."


def _heuristic_deep(raw: RawItem) -> str:
    if raw.summary:
        return raw.summary
    return "Set OPENAI_API_KEY to generate an expanded abstract-style explanation for this item."


def _fallback_brief(items: list[IntelligenceItem], trends: list[Trend]) -> str:
    lines = ["# Important Tech, Science, and AI Signals", ""]
    for section, categories in {
        "Must Know Today": None,
        "Research Papers and Breakthroughs": {"research"},
        "AI and Infrastructure": {"ai_labs", "big_tech"},
        "Tools and Engineering": {"tools", "deep_tech_learning"},
        "Science, Quantum, and Curiosity": {"science_and_tech"},
        "Markets and Company Strategy": {"markets", "business_and_markets"},
        "Videos Worth Learning From": {"videos"},
    }.items():
        lines.extend([f"## {section}", ""])
        selected = items[:5] if categories is None else [i for i in items if i.category in categories][:5]
        for item in selected:
            lines.extend(
                [
                    f"### {item.title}",
                    f"Score: {item.importance_score}/100 | Source: [{item.source}]({item.url})",
                    f"**Type:** {item.analysis_type}",
                    f"**What happened:** {item.what_happened}",
                    f"**Why it matters:** {item.why_it_matters}",
                    f"**How it works:** {item.how_it_works}",
                    f"**Expanded how it works:** {item.deep_explanation}",
                    f"**Learning value:** {item.learning_value}",
                    f"**Watch next:** {item.what_to_watch}",
                    "",
                ]
            )
    lines.extend(["## Emerging Trends", ""])
    for trend in trends:
        lines.append(f"- **{trend.topic}**: {trend.explanation}")
    return "\n".join(lines)


def _fallback_research(topic: str, items: list[RawItem]) -> str:
    lines = [f"# Research Brief: {topic}", "", "## Best Recent Sources", ""]
    for item in items[:10]:
        lines.append(f"- [{item.title}]({item.url}) - {item.summary[:240]}")
    lines.append("\nSet `OPENAI_API_KEY` for a full synthesized explanation.")
    return "\n".join(lines)
