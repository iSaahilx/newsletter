# Personal Intelligence System

A personal AI, technology, science, research, startup, tools, markets, and curiosity intelligence system.

This is not a generic newsletter. It is designed to answer:

- What happened, if this is news?
- How does it work, if this is research or a technical breakthrough?
- Why is this worth learning?
- What should I watch next?

It fetches high-signal sources, removes duplicates, scores importance, stores history, detects emerging trends, writes a Markdown brief, and generates a local expandable dashboard.

## What It Covers

- AI labs: OpenAI, Anthropic, Google Research, DeepMind, Meta AI, Mistral, Cohere
- Universities: Stanford HAI, MIT, Berkeley, CMU, Oxford
- Big tech and semiconductors: NVIDIA, Microsoft Research, Amazon Science, Apple ML, IBM Research
- Research: arXiv AI/ML/NLP/robotics/quantum, Hugging Face Papers, Papers with Code
- Tools and AI engineering: GitHub Trending, Hacker News, Product Hunt, LangChain, LlamaIndex, Weights and Biases, Simon Willison, Modal, Replicate
- Engineering and deep tech: InfoQ, Google Cloud, Google Developers, KDnuggets, Towards Data Science, MarkTechPost, Netflix TechBlog, Cloudflare, Meta Engineering, Uber Engineering
- Science and curiosity: MIT Tech Review, Ars Technica, IEEE Spectrum, Nature, ScienceDaily, Phys.org, SciTechDaily, Quanta, Nautilus, The Quantum Insider
- Videos: Veritasium, Two Minute Papers, Computerphile, PBS Space Time, Welch Labs
- Business and markets: TechCrunch, VentureBeat, CNBC Tech, large moves in tracked stocks

Edit `sources.yaml` to add or remove sources, tickers, and interests.

## Architecture

```text
GitHub Actions cron or local machine
    -> RSS / arXiv / market fetchers
    -> SQLite history store
    -> duplicate filtering
    -> OpenAI small model scoring
    -> topic and entity extraction
    -> trend detection
    -> OpenAI large model final brief
    -> Markdown output + expandable HTML dashboard
```

SQLite is the default because it works locally and inside GitHub Actions. If you later want Supabase/Postgres, keep the same model objects and replace `intelligence/db.py`.

## Setup

```bash
cd personal-intelligence-system
python -m venv .venv
.venv\Scripts\activate
pip install -e .
copy .env.example .env
```

Add your key to `.env`:

```bash
OPENAI_API_KEY=sk-your-key
```

Initialize the database:

```bash
python -m intelligence init
```

Generate a daily brief:

```bash
python -m intelligence daily
```

The latest brief and dashboard are written to:

```text
output/latest.md
output/dashboard.html
```

`daily` automatically creates both files. You do not need to run a separate dashboard command after `daily`.

## Running It Again

Use this when you want a fresh fetch, new scoring, a new Markdown brief, and a new dashboard:

```bash
python -m intelligence daily
```

This is the main command. It fetches sources, stores raw items, scores new items, updates trends, writes `output/latest.md`, and regenerates `output/dashboard.html`.

If you changed prompts, source lists, model names, scoring thresholds, or added your OpenAI key after an earlier no-key run, reanalyze stored items:

```bash
python -m intelligence reanalyze --limit 120
```

Then regenerate the dashboard if needed:

```bash
python -m intelligence dashboard
```

Usually the best sequence after improving prompts or adding your API key is:

```bash
python -m intelligence daily
python -m intelligence reanalyze --limit 120
python -m intelligence dashboard
```

If you want to truly start over from an empty local history, delete the SQLite database and run again:

```powershell
Remove-Item .\data\intelligence.sqlite3 -ErrorAction SilentlyContinue
python -m intelligence init
python -m intelligence daily
```

Only do this if you do not care about the old stored history and trend baseline.

## GitHub Actions

Yes, GitHub Actions cron works well for this.

1. Push this directory to a GitHub repo.
2. Add a repository secret named `OPENAI_API_KEY`.
3. Enable Actions.
4. The workflow in `.github/workflows/daily-intelligence.yml` runs every day at `02:00 UTC`.
5. Use the manual `workflow_dispatch` button to test it immediately.

The model runs inside the GitHub Actions runner when the cron job executes. Your OpenAI key is injected from GitHub Secrets. The generated brief and SQLite history are committed back to the repo under `output/` and `data/`.

## Host The Dashboard

The repository includes a GitHub Pages workflow at `.github/workflows/pages.yml`. It deploys the `output/` folder, so `output/dashboard.html` becomes accessible from your phone.

First push the project to GitHub:

```bash
git init
git add .
git commit -m "Create personal intelligence system"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/personal-intelligence-system.git
git push -u origin main
```

Then in GitHub:

1. Open the repository settings.
2. Go to `Pages`.
3. Set source to `GitHub Actions`.
4. Push again or run the `Publish Dashboard` workflow manually.

After it deploys, GitHub will show a Pages URL. The dashboard is usually available at:

```text
https://YOUR_USERNAME.github.io/personal-intelligence-system/dashboard.html
```

For your current workflow, run locally and push the updated dashboard:

```bash
python -m intelligence daily
git add output/dashboard.html output/latest.md output/.nojekyll
git commit -m "Update intelligence dashboard"
git push
```

The push triggers GitHub Pages, and the phone-accessible webpage updates.

## Commands

Generate the daily intelligence brief:

```bash
python -m intelligence daily
```

This also creates `output/dashboard.html` automatically.

Research a specific topic:

```bash
python -m intelligence research "Mixture of Experts"
python -m intelligence research "Quantum error correction"
python -m intelligence research "Model Context Protocol"
```

Show top stored items:

```bash
python -m intelligence top --limit 20
```

Regenerate the dashboard from stored history without fetching:

```bash
python -m intelligence dashboard
```

This command exists so you can rebuild the dashboard after changing dashboard styling or after reanalysis, without spending time or API calls fetching/scoring news again.

Upgrade previously fetched items with the newest prompts after adding an OpenAI key:

```bash
python -m intelligence reanalyze --limit 120
```

This does not fetch new sources. It takes already stored raw items, runs the current model prompts again, saves richer explanations, and regenerates the dashboard.

Ask what the system has stored about an entity:

```bash
python -m intelligence entity NVIDIA
python -m intelligence entity Stanford
python -m intelligence entity MIT
```

## Model Strategy

The pipeline uses two model tiers:

- `OPENAI_SMALL_MODEL`: scoring, filtering, topic extraction, entity extraction
- `OPENAI_LARGE_MODEL`: final daily brief and research reports

This keeps costs lower because the large model only sees filtered high-signal items.

Recommended fast/cheap `.env` values:

```bash
OPENAI_SMALL_MODEL=gpt-4.1-nano
OPENAI_LARGE_MODEL=gpt-4.1-mini
SCORING_ITEM_LIMIT=72
FINAL_BRIEF_ITEM_LIMIT=28
```

If your `.env` still has `OPENAI_LARGE_MODEL=gpt-4.1`, change it to `gpt-4.1-mini` to avoid token-per-minute failures during final synthesis.

`MAX_ITEMS_PER_RUN` controls the maximum fresh items considered, but `SCORING_ITEM_LIMIT` is the hard cap for model scoring. The pipeline pre-ranks fetched items first, then sends only the highest-signal items to the model.

Without `OPENAI_API_KEY`, the system still runs with heuristic scoring, but the output is much less useful.

## How The Output Adapts

The system no longer forces every item into the same four labels.

- Research papers and technical breakthroughs get an expanded abstract-style mechanism explanation.
- Engineering stories get the system design, failure mode, or lesson.
- Videos and explainers get the story, core idea, and reason to watch.
- Market moves get likely drivers, second-order effects, and what to watch.
- General news stays compact.

## How Importance Scoring Works

Each item gets:

- novelty score
- technical significance score
- business significance score
- long-term importance score
- final importance score

Only items above `MIN_IMPORTANCE_SCORE` are kept for the daily brief. Default is `70`.

`RSS_ITEMS_PER_SOURCE` controls how far back each feed is sampled. Default is `20`, which helps catch strong older items instead of only same-day posts.

## How Filtering Works

The system does not send all fetched items to OpenAI. The flow is:

```text
all fetched items
  -> raw dedupe
  -> remove already-scored URLs
  -> local priority ranking
  -> top SCORING_ITEM_LIMIT items
  -> OpenAI scoring
  -> keep items above MIN_IMPORTANCE_SCORE
  -> event dedupe
  -> final brief/dashboard
```

If a run fetches 1127 items, the first reduction is local and cheap. The system removes exact URL duplicates, normalized-title duplicates, and near-duplicate titles. Near duplicates use fuzzy title similarity against recent kept items.

Then it ignores items already present in `intelligence_items`, so old scored links are not repeatedly sent to the model.

Then `_raw_priority_score()` ranks fresh items before model scoring. The current local boosts are:

- `research`: `+30`
- `ai_labs`: `+25`
- `deep_tech_learning`: `+24`
- `videos`: `+22`
- `science_and_tech`: `+20`
- `tools`: `+18`
- `big_tech`: `+16`
- `markets`: `+12`
- `business_and_markets`: `+10`

It also boosts titles/summaries containing important terms:

- `agent`: `+12`
- `quantum`: `+12`
- `breakthrough`: `+12`
- `llm`, `reasoning`, `robot`, `infrastructure`, `nvidia`, `openai`, `anthropic`, `scaling law`, `backdoor`: extra boosts
- longer summaries get a small boost because they usually contain more usable context
- newer items get a tiny timestamp boost as a tie-breaker

After that, only the top `SCORING_ITEM_LIMIT` items are sent to the small model. Default is:

```bash
SCORING_ITEM_LIMIT=72
```

The model then gives each item `importance_score`, `novelty_score`, `technical_score`, `business_score`, and `long_term_score`. Only items above `MIN_IMPORTANCE_SCORE` are saved as important.

The final brief does not send every saved item either. It sends only a compact payload for the top `FINAL_BRIEF_ITEM_LIMIT` items:

```bash
FINAL_BRIEF_ITEM_LIMIT=28
```

This prevents token-per-minute failures and keeps the run cheaper.

## How Fetching Works

Most sources are not searched with a general search API. They are fetched directly:

- RSS/Atom feeds are fetched with `httpx` and parsed with `feedparser`.
- Some blocked or no-RSS sources use Google News RSS search URLs, for example `Anthropic research AI` or `MIT quantum research`.
- arXiv uses the arXiv API, not RSS, because arXiv RSS returned empty results.
- Hugging Face Papers uses the public papers page and extracts paper links.
- Market moves come from Stooq CSV quotes for tracked tickers.
- YouTube channels use YouTube RSS feeds.

So it is a mix of direct feeds, targeted Google News RSS feeds, arXiv API, page extraction for Hugging Face Papers, and market CSV data.

## Trend Detection

The system stores extracted topics every day. It compares the last 7 days against the previous 30-day baseline.

Example:

```text
MCP mentions:
previous baseline: 11
last week: 87
trend: emerging
```

This turns repeated weak signals into a visible trend.

## Market Moves

Tracked tickers live in `sources.yaml`.

If a stock moves more than `MARKET_MOVE_THRESHOLD_PERCENT` intraday, the system adds it as an intelligence item. The daily brief then explains likely drivers using the broader news context.

## Extending It

Good next upgrades:

- Add email delivery using SMTP, Resend, or Buttondown.
- Swap SQLite for Supabase/Postgres.
- Add embeddings for semantic search over saved history.
- Add a small web UI over `output/latest.md` and the SQLite database.
- Add specialized fetchers for SEC filings, funding rounds, Semantic Scholar, and company blogs that do not expose RSS.
- Add a real graph database if entity relationships become central.
