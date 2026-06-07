from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from pathlib import Path

from intelligence.models import IntelligenceItem, Trend


SECTIONS: dict[str, set[str] | None] = {
    "Must Know": None,
    "Research Papers": {"research_paper", "technical_breakthrough"},
    "AI Infrastructure": {"tool_or_framework", "company_strategy"},
    "Engineering Stories": {"engineering_story"},
    "Science and Curiosity": {"science_explainer"},
    "Videos Worth Watching": {"learning_video"},
    "Markets": {"market_move"},
}


def render_dashboard(
    output_dir: Path,
    items: list[IntelligenceItem],
    trends: list[Trend],
    markdown_name: str = "latest.md",
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    cards = "\n".join(_render_section(title, _select_items(items, types)) for title, types in SECTIONS.items())
    trend_cards = "\n".join(_render_trend(trend) for trend in trends) or "<p>No emerging trend yet.</p>"
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Personal Intelligence Dashboard</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #0b1020;
      --panel: #121a2f;
      --panel-2: #18223a;
      --text: #eef3ff;
      --muted: #aab5cc;
      --accent: #8bd3ff;
      --good: #8df0b3;
      --border: #263657;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: radial-gradient(circle at top left, #19264a 0, var(--bg) 42%);
      color: var(--text);
    }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 32px 20px 64px; }}
    header {{ display: grid; gap: 12px; margin-bottom: 28px; }}
    h1 {{ margin: 0; font-size: clamp(2rem, 5vw, 4.2rem); letter-spacing: -0.06em; }}
    h2 {{ margin: 36px 0 14px; font-size: 1.35rem; }}
    p {{ color: var(--muted); line-height: 1.6; }}
    a {{ color: var(--accent); }}
    .toolbar {{
      display: flex; gap: 12px; flex-wrap: wrap; align-items: center;
      padding: 14px; background: rgba(18, 26, 47, 0.75); border: 1px solid var(--border);
      border-radius: 18px; position: sticky; top: 10px; z-index: 2; backdrop-filter: blur(14px);
    }}
    input, select {{
      background: var(--panel-2); color: var(--text); border: 1px solid var(--border);
      border-radius: 12px; padding: 11px 12px; min-width: 220px;
    }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(310px, 1fr)); gap: 16px; }}
    .card {{
      background: linear-gradient(180deg, rgba(24, 34, 58, 0.96), rgba(18, 26, 47, 0.96));
      border: 1px solid var(--border); border-radius: 20px; padding: 18px;
      box-shadow: 0 14px 40px rgba(0,0,0,0.22);
    }}
    .card h3 {{ margin: 8px 0 8px; font-size: 1.05rem; line-height: 1.35; }}
    .meta {{ display: flex; gap: 8px; flex-wrap: wrap; color: var(--muted); font-size: 0.82rem; }}
    .pill {{ border: 1px solid var(--border); border-radius: 999px; padding: 4px 8px; }}
    .score {{ color: var(--good); font-weight: 700; }}
    .summary strong {{ color: var(--text); }}
    details {{
      margin-top: 12px; border-top: 1px solid var(--border); padding-top: 12px;
    }}
    summary {{ cursor: pointer; color: var(--accent); font-weight: 650; }}
    .deep {{ white-space: pre-wrap; color: #d9e4fb; }}
    .trend {{ border-left: 3px solid var(--accent); }}
    .empty {{ color: var(--muted); font-style: italic; }}
  </style>
</head>
<body>
<main>
  <header>
    <p>Generated {escape(generated_at)}</p>
    <h1>Personal Intelligence Dashboard</h1>
    <p>Strong AI, research, engineering, science, markets, and curiosity signals. Cards are expandable when the idea needs a real explanation, not just a one-line summary.</p>
    <p><a href="{escape(markdown_name)}">Open Markdown Brief</a></p>
  </header>
  <section class="toolbar" aria-label="filters">
    <input id="search" type="search" placeholder="Search topics, sources, entities...">
    <select id="type">
      <option value="">All types</option>
      {''.join(f'<option value="{escape(t)}">{escape(t.replace("_", " ").title())}</option>' for t in sorted({item.analysis_type for item in items}))}
    </select>
  </section>
  <section>
    <h2>Emerging Trends</h2>
    <div class="grid">{trend_cards}</div>
  </section>
  {cards}
</main>
<script>
const search = document.querySelector("#search");
const type = document.querySelector("#type");
const cards = [...document.querySelectorAll(".card[data-search]")];
function applyFilters() {{
  const q = search.value.toLowerCase();
  const t = type.value;
  for (const card of cards) {{
    const matchesText = card.dataset.search.includes(q);
    const matchesType = !t || card.dataset.type === t;
    card.style.display = matchesText && matchesType ? "" : "none";
  }}
}}
search.addEventListener("input", applyFilters);
type.addEventListener("change", applyFilters);
</script>
</body>
</html>"""
    path = output_dir / "dashboard.html"
    path.write_text(html, encoding="utf-8")
    return path


def _select_items(items: list[IntelligenceItem], types: set[str] | None) -> list[IntelligenceItem]:
    if types is None:
        return items[:8]
    return [item for item in items if item.analysis_type in types][:12]


def _render_section(title: str, items: list[IntelligenceItem]) -> str:
    rendered = "\n".join(_render_card(item) for item in items)
    if not rendered:
        rendered = '<p class="empty">No matching items yet. More runs will fill this section.</p>'
    return f"<section><h2>{escape(title)}</h2><div class=\"grid\">{rendered}</div></section>"


def _render_card(item: IntelligenceItem) -> str:
    deep = item.deep_explanation or item.how_it_works
    search_blob = " ".join(
        [
            item.title,
            item.source,
            item.category,
            item.analysis_type,
            " ".join(item.topics),
            " ".join(item.entities),
        ]
    ).lower()
    hook = f"<p><strong>Hook:</strong> {escape(item.story_hook)}</p>" if item.story_hook else ""
    learning = (
        f"<p><strong>Learning value:</strong> {escape(item.learning_value)}</p>"
        if item.learning_value
        else ""
    )
    return f"""
<article class="card" data-type="{escape(item.analysis_type)}" data-search="{escape(search_blob)}">
  <div class="meta">
    <span class="pill score">{item.importance_score}/100</span>
    <span class="pill">{escape(item.analysis_type.replace("_", " ").title())}</span>
    <span class="pill">{escape(item.source)}</span>
  </div>
  <h3><a href="{escape(item.url)}" target="_blank" rel="noreferrer">{escape(item.title)}</a></h3>
  {hook}
  <div class="summary">
    <p><strong>Signal:</strong> {escape(item.what_happened)}</p>
    <p><strong>Why it matters:</strong> {escape(item.why_it_matters)}</p>
    <p><strong>How it works:</strong> {escape(item.how_it_works)}</p>
  </div>
  <details>
    <summary>Expanded explanation</summary>
    <p class="deep">{escape(deep)}</p>
    {learning}
    <p><strong>Watch next:</strong> {escape(item.what_to_watch)}</p>
  </details>
</article>"""


def _render_trend(trend: Trend) -> str:
    return f"""
<article class="card trend">
  <div class="meta"><span class="pill score">{trend.lift}x lift</span></div>
  <h3>{escape(trend.topic.title())}</h3>
  <p>{escape(trend.explanation)}</p>
  <p>Recent mentions: {trend.recent_count}. Baseline mentions: {trend.baseline_count}.</p>
</article>"""
