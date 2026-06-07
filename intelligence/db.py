from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from intelligence.models import IntelligenceItem, RawItem, Trend


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS raw_items (
            url TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            source TEXT NOT NULL,
            category TEXT NOT NULL,
            kind TEXT NOT NULL,
            summary TEXT,
            authors_json TEXT NOT NULL,
            published_at TEXT NOT NULL,
            fetched_at TEXT NOT NULL,
            metadata_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS intelligence_items (
            url TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            source TEXT NOT NULL,
            category TEXT NOT NULL,
            kind TEXT NOT NULL,
            summary TEXT,
            published_at TEXT NOT NULL,
            fetched_at TEXT NOT NULL,
            canonical_event TEXT NOT NULL,
            analysis_type TEXT NOT NULL DEFAULT 'news',
            story_hook TEXT NOT NULL DEFAULT '',
            what_happened TEXT NOT NULL,
            why_it_matters TEXT NOT NULL,
            how_it_works TEXT NOT NULL,
            deep_explanation TEXT NOT NULL DEFAULT '',
            learning_value TEXT NOT NULL DEFAULT '',
            what_to_watch TEXT NOT NULL,
            importance_score INTEGER NOT NULL,
            novelty_score INTEGER NOT NULL,
            technical_score INTEGER NOT NULL,
            business_score INTEGER NOT NULL,
            long_term_score INTEGER NOT NULL,
            entities_json TEXT NOT NULL,
            topics_json TEXT NOT NULL,
            reasoning TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS topic_mentions (
            topic TEXT NOT NULL,
            item_url TEXT NOT NULL,
            mentioned_at TEXT NOT NULL,
            PRIMARY KEY (topic, item_url)
        );

        CREATE TABLE IF NOT EXISTS entity_mentions (
            entity TEXT NOT NULL,
            item_url TEXT NOT NULL,
            mentioned_at TEXT NOT NULL,
            PRIMARY KEY (entity, item_url)
        );

        CREATE TABLE IF NOT EXISTS brief_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            generated_at TEXT NOT NULL,
            title TEXT NOT NULL,
            markdown TEXT NOT NULL
        );
        """
    )
    _ensure_column(conn, "intelligence_items", "analysis_type", "TEXT NOT NULL DEFAULT 'news'")
    _ensure_column(conn, "intelligence_items", "story_hook", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "intelligence_items", "deep_explanation", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "intelligence_items", "learning_value", "TEXT NOT NULL DEFAULT ''")
    conn.commit()


def _ensure_column(
    conn: sqlite3.Connection,
    table: str,
    column: str,
    declaration: str,
) -> None:
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")


def upsert_raw_items(conn: sqlite3.Connection, items: list[RawItem]) -> int:
    count = 0
    for item in items:
        conn.execute(
            """
            INSERT OR IGNORE INTO raw_items (
                url, title, source, category, kind, summary, authors_json,
                published_at, fetched_at, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item.url,
                item.title,
                item.source,
                item.category,
                item.kind.value,
                item.summary,
                json.dumps(item.authors),
                item.published_at.isoformat(),
                item.fetched_at.isoformat(),
                json.dumps(item.metadata),
            ),
        )
        count += conn.total_changes
    conn.commit()
    return count


def item_seen(conn: sqlite3.Connection, url: str) -> bool:
    row = conn.execute("SELECT 1 FROM intelligence_items WHERE url = ?", (url,)).fetchone()
    return row is not None


def save_intelligence_items(conn: sqlite3.Connection, items: list[IntelligenceItem]) -> None:
    now = datetime.now(timezone.utc).isoformat()
    for item in items:
        conn.execute(
            """
            INSERT OR REPLACE INTO intelligence_items (
                url, title, source, category, kind, summary, published_at, fetched_at,
                canonical_event, analysis_type, story_hook, what_happened, why_it_matters,
                how_it_works, deep_explanation, learning_value, what_to_watch, importance_score,
                novelty_score, technical_score, business_score, long_term_score, entities_json,
                topics_json, reasoning, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item.url,
                item.title,
                item.source,
                item.category,
                item.kind.value,
                item.summary,
                item.published_at.isoformat(),
                item.fetched_at.isoformat(),
                item.canonical_event,
                item.analysis_type,
                item.story_hook,
                item.what_happened,
                item.why_it_matters,
                item.how_it_works,
                item.deep_explanation,
                item.learning_value,
                item.what_to_watch,
                item.importance_score,
                item.novelty_score,
                item.technical_score,
                item.business_score,
                item.long_term_score,
                json.dumps(item.entities),
                json.dumps(item.topics),
                item.reasoning,
                now,
            ),
        )
        for topic in item.topics:
            conn.execute(
                "INSERT OR IGNORE INTO topic_mentions (topic, item_url, mentioned_at) VALUES (?, ?, ?)",
                (topic.lower().strip(), item.url, item.published_at.isoformat()),
            )
        for entity in item.entities:
            conn.execute(
                """
                INSERT OR IGNORE INTO entity_mentions (entity, item_url, mentioned_at)
                VALUES (?, ?, ?)
                """,
                (entity.lower().strip(), item.url, item.published_at.isoformat()),
            )
    conn.commit()


def recent_items(conn: sqlite3.Connection, limit: int = 60) -> list[IntelligenceItem]:
    rows = conn.execute(
        """
        SELECT * FROM intelligence_items
        ORDER BY importance_score DESC, published_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [_row_to_item(row) for row in rows]


def recent_raw_items(conn: sqlite3.Connection, limit: int = 120) -> list[RawItem]:
    rows = conn.execute(
        """
        SELECT * FROM raw_items
        ORDER BY published_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [_row_to_raw_item(row) for row in rows]


def save_brief(conn: sqlite3.Connection, title: str, markdown: str) -> None:
    conn.execute(
        "INSERT INTO brief_runs (generated_at, title, markdown) VALUES (?, ?, ?)",
        (datetime.now(timezone.utc).isoformat(), title, markdown),
    )
    conn.commit()


def detect_trends(conn: sqlite3.Connection) -> list[Trend]:
    now = datetime.now(timezone.utc)
    recent_cutoff = (now - timedelta(days=7)).isoformat()
    baseline_cutoff = (now - timedelta(days=37)).isoformat()
    rows = conn.execute(
        """
        WITH recent AS (
            SELECT topic, COUNT(*) AS c
            FROM topic_mentions
            WHERE mentioned_at >= ?
            GROUP BY topic
        ),
        baseline AS (
            SELECT topic, COUNT(*) AS c
            FROM topic_mentions
            WHERE mentioned_at >= ?
              AND mentioned_at < ?
            GROUP BY topic
        )
        SELECT recent.topic,
               recent.c AS recent_count,
               COALESCE(baseline.c, 0) AS baseline_count
        FROM recent
        LEFT JOIN baseline ON baseline.topic = recent.topic
        WHERE recent.c >= 2
        ORDER BY recent.c DESC
        LIMIT 10
        """,
        (recent_cutoff, baseline_cutoff, recent_cutoff),
    ).fetchall()
    trends: list[Trend] = []
    for row in rows:
        baseline_weekly = max(row["baseline_count"] / 4.0, 0.25)
        lift = round(row["recent_count"] / baseline_weekly, 2)
        if lift >= 1.75:
            trends.append(
                Trend(
                    topic=row["topic"],
                    recent_count=row["recent_count"],
                    baseline_count=row["baseline_count"],
                    lift=lift,
                    explanation=f"Mentions rose {lift}x versus the previous monthly baseline.",
                )
            )
    return trends


def items_for_entity(conn: sqlite3.Connection, entity: str, limit: int = 20) -> list[IntelligenceItem]:
    rows = conn.execute(
        """
        SELECT intelligence_items.*
        FROM intelligence_items
        JOIN entity_mentions ON entity_mentions.item_url = intelligence_items.url
        WHERE entity_mentions.entity = ?
        ORDER BY intelligence_items.published_at DESC
        LIMIT ?
        """,
        (entity.lower().strip(), limit),
    ).fetchall()
    return [_row_to_item(row) for row in rows]


def _row_to_item(row: sqlite3.Row) -> IntelligenceItem:
    return IntelligenceItem(
        title=row["title"],
        url=row["url"],
        source=row["source"],
        category=row["category"],
        kind=row["kind"],
        summary=row["summary"] or "",
        published_at=datetime.fromisoformat(row["published_at"]),
        fetched_at=datetime.fromisoformat(row["fetched_at"]),
        canonical_event=row["canonical_event"],
        analysis_type=row["analysis_type"] or "news",
        story_hook=row["story_hook"] or "",
        what_happened=row["what_happened"],
        why_it_matters=row["why_it_matters"],
        how_it_works=row["how_it_works"],
        deep_explanation=row["deep_explanation"] or "",
        learning_value=row["learning_value"] or "",
        what_to_watch=row["what_to_watch"],
        importance_score=row["importance_score"],
        novelty_score=row["novelty_score"],
        technical_score=row["technical_score"],
        business_score=row["business_score"],
        long_term_score=row["long_term_score"],
        entities=json.loads(row["entities_json"]),
        topics=json.loads(row["topics_json"]),
        reasoning=row["reasoning"] or "",
    )


def _row_to_raw_item(row: sqlite3.Row) -> RawItem:
    return RawItem(
        title=row["title"],
        url=row["url"],
        source=row["source"],
        category=row["category"],
        kind=row["kind"],
        summary=row["summary"] or "",
        authors=json.loads(row["authors_json"]),
        published_at=datetime.fromisoformat(row["published_at"]),
        fetched_at=datetime.fromisoformat(row["fetched_at"]),
        metadata=json.loads(row["metadata_json"]),
    )
