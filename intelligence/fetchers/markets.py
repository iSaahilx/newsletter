from __future__ import annotations

import csv
from datetime import datetime, timezone
from io import StringIO

import httpx

from intelligence.models import ItemKind, RawItem
from intelligence.progress import log, warn


async def fetch_market_moves(
    tickers: list[str],
    threshold_percent: float,
    timeout_seconds: float = 20.0,
) -> list[RawItem]:
    """Fetch large daily moves from Stooq's free quote endpoint.

    These are treated as intelligence events; the model later explains likely
    causes using the broader news context fetched in the same run.
    """

    if not tickers:
        return []
    log(f"Fetching market moves for {len(tickers)} tickers...")
    symbols = ",".join(f"{ticker.lower()}.us" for ticker in tickers)
    url = f"https://stooq.com/q/l/?s={symbols}&f=sd2t2ohlcv&h&e=csv"
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
    except Exception:
        warn("Market fetch failed; continuing without market-move items")
        return []

    items: list[RawItem] = []
    for row in csv.DictReader(StringIO(response.text)):
        try:
            close = float(row["Close"])
            open_price = float(row["Open"])
        except Exception:
            continue
        if open_price <= 0:
            continue
        change_pct = ((close - open_price) / open_price) * 100
        if abs(change_pct) < threshold_percent:
            continue
        ticker = row["Symbol"].split(".")[0].upper()
        direction = "rose" if change_pct > 0 else "fell"
        title = f"{ticker} {direction} {abs(change_pct):.1f}% intraday"
        items.append(
            RawItem(
                title=title,
                url=f"https://stooq.com/q/?s={ticker.lower()}.us",
                source="Stooq Market Data",
                category="markets",
                kind=ItemKind.MARKET,
                summary=(
                    f"{ticker} opened at {open_price:.2f} and last traded at {close:.2f}, "
                    f"a {change_pct:+.1f}% move. Investigate company news, sector news, "
                    "earnings, analyst changes, and macro drivers."
                ),
                published_at=datetime.now(timezone.utc),
                metadata={
                    "ticker": ticker,
                    "open": open_price,
                    "close": close,
                    "change_percent": round(change_pct, 2),
                    "volume": row.get("Volume") or "",
                },
            )
        )
    log(f"Finished market fetch: {len(items)} large moves above {threshold_percent}%")
    return items
