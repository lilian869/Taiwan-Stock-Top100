"""Daily Top 100 collection and static dashboard data generation."""
from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from src.backfill import fetch_day
from src.data_sources import (
    create_session,
    fetch_stock_universe,
    fetch_valuations,
    filter_quotes_by_universe,
)
from src.indicators import calculate

ROOT = Path(__file__).resolve().parents[1]
HISTORY = ROOT / "data" / "history"
OUTPUT = ROOT / "docs" / "data" / "latest.json"
MIN_LISTED_QUOTES = 500
MIN_OTC_QUOTES = 200
MAX_LOOKBACK_DAYS = 10


def fetch_latest_complete_quotes(
    *,
    today: date | None = None,
    max_lookback_days: int = MAX_LOOKBACK_DAYS,
    day_fetch: Callable | None = None,
    session_factory: Callable | None = None,
    universe_fetch: Callable | None = None,
) -> tuple[list[dict], list[dict], str]:
    """Fetch both markets for one explicit date; fall back only to an earlier complete day."""
    if max_lookback_days < 0:
        raise ValueError("max_lookback_days must be >= 0")

    # GitHub runners use UTC; choose the trading date in Taiwan local time.
    if today is None:
        today = datetime.now(ZoneInfo("Asia/Taipei")).date()

    day_fetch = day_fetch or fetch_day
    session_factory = session_factory or create_session
    universe_fetch = universe_fetch or fetch_stock_universe

    session = session_factory()
    universe = universe_fetch(session)

    for offset in range(max_lookback_days + 1):
        trade_day = today - timedelta(days=offset)
        if trade_day.weekday() >= 5:
            continue

        try:
            raw_quotes = day_fetch(session, trade_day)
            eligible_quotes = filter_quotes_by_universe(raw_quotes, universe)
            listed_count = sum(row.get("market") == "上市" for row in eligible_quotes)
            otc_count = sum(row.get("market") == "上櫃" for row in eligible_quotes)
            if listed_count < MIN_LISTED_QUOTES or otc_count < MIN_OTC_QUOTES:
                raise ValueError(
                    f"incomplete market coverage: listed={listed_count}, OTC={otc_count}"
                )
            print(
                f"[OK] complete dated snapshot={trade_day.isoformat()}; "
                f"listed={listed_count}; OTC={otc_count}; eligible={len(eligible_quotes)}"
            )
            return raw_quotes, eligible_quotes, trade_day.isoformat()
        except Exception as exc:
            print(f"[WARN] {trade_day.isoformat()} unavailable/incomplete: {exc}")

    raise RuntimeError(
        f"No complete TWSE+TPEx snapshot found in the last "
        f"{max_lookback_days + 1} calendar days; refusing to publish."
    )


def load_history() -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    if not HISTORY.exists():
        return grouped
    for path in sorted(HISTORY.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            for row in payload.get("quotes", []):
                grouped.setdefault(row["code"], []).append(
                    {
                        "date": payload["date"],
                        "close": row["close"],
                        "high": row.get("high"),
                        "low": row.get("low"),
                        "volume": row.get("volume"),
                    }
                )
        except (OSError, ValueError, KeyError, TypeError) as exc:
            print(f"[WARN] skipping unreadable history {path.name}: {exc}")
    return grouped


def main() -> None:
    print("[INFO] collecting dated TWSE + TPEx daily closing quotes")
    raw_quotes, quotes, trade_date = fetch_latest_complete_quotes()

    quotes = [dict(row) for row in quotes]
    for row in quotes:
        row.pop("date", None)
    quotes.sort(key=lambda row: row["volume"], reverse=True)
    top100 = quotes[:100]

    valuations = fetch_valuations()
    for row in top100:
        row.update(valuations.get(row["code"], {}))

    HISTORY.mkdir(parents=True, exist_ok=True)
    snapshot = {
        "date": trade_date,
        "source": ["TWSE dated MI_INDEX", "TPEx dated afterTrading/otc"],
        "universe_source": [
            "TWSE listed company master t187ap03_L",
            "TPEx OTC stock master mopsfin_t187ap03_O",
        ],
        "raw_quote_count": len(raw_quotes),
        "eligible_quote_count": len(quotes),
        "quotes": quotes,
    }
    (HISTORY / f"{trade_date}.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    history = load_history()
    history_output = ROOT / "docs" / "data" / "stock_history"
    history_output.mkdir(parents=True, exist_ok=True)
    for row in top100:
        stock_history = sorted(history.get(row["code"], []), key=lambda item: item["date"])
        row["technical"] = calculate(stock_history)
        history_payload = {
            "code": row["code"],
            "name": row["name"],
            "market": row["market"],
            "source": "Locally stored daily TWSE/TPEx closing snapshots",
            "history": stock_history,
        }
        (history_output / f"{row['code']}.json").write_text(
            json.dumps(history_payload, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )

    payload = {
        "date": trade_date,
        "market_data_type": "daily_close",
        "universe_rule": (
            "Official TWSE listed company master + TPEx OTC stock master; "
            "daily traded shares descending; top 100"
        ),
        "raw_market_quote_count": len(raw_quotes),
        "eligible_stock_quote_count": len(quotes),
        "top100": top100,
        "notes": [
            "Universe is restricted to codes present in official listed/OTC company master lists; non-company instruments such as ETFs and warrants are excluded.",
            "Daily closing data, not intraday real-time quotes.",
            "Both markets are fetched for the same explicit trading date from dated historical endpoints; incomplete market coverage is rejected.",
            "Technical indicators use locally stored daily snapshots; they remain null until sufficient history exists.",
            "Historical backfill target is 120 trading-day snapshots.",
            "Full financial-statement metrics are not yet integrated; PE/dividend yield/PB are optional enrichment.",
        ],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        f"[OK] date={trade_date}; raw={len(raw_quotes)}; "
        f"eligible={len(quotes)}; Top100={len(top100)}"
    )


if __name__ == "__main__":
    main()
