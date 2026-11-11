"""Daily Top 100 collection and static dashboard data generation."""
from __future__ import annotations
import json
import time
from pathlib import Path
from collections.abc import Callable
from src.data_sources import (
    fetch_twse_quotes, fetch_tpex_quotes, fetch_valuations,
    fetch_stock_universe, filter_quotes_by_universe,
)
from src.indicators import calculate

ROOT = Path(__file__).resolve().parents[1]
HISTORY = ROOT / "data" / "history"
OUTPUT = ROOT / "docs" / "data" / "latest.json"
DATE_SYNC_ATTEMPTS = 10
DATE_SYNC_WAIT_SECONDS = 120


def fetch_aligned_quotes(
    twse_fetch: Callable[[], list[dict]] = fetch_twse_quotes,
    tpex_fetch: Callable[[], list[dict]] = fetch_tpex_quotes,
    *,
    max_attempts: int = DATE_SYNC_ATTEMPTS,
    wait_seconds: int = DATE_SYNC_WAIT_SECONDS,
) -> tuple[list[dict], list[dict], str]:
    """Wait for both official sources to publish the same trading date; never mix dates."""
    if max_attempts < 1 or wait_seconds < 0:
        raise ValueError("max_attempts must be >= 1 and wait_seconds must be >= 0")
    for attempt in range(1, max_attempts + 1):
        twse, tpex = twse_fetch(), tpex_fetch()
        dates_twse = {row["date"] for row in twse}
        dates_tpex = {row["date"] for row in tpex}
        if len(dates_twse) != 1 or len(dates_tpex) != 1:
            raise ValueError(f"Unexpected mixed source dates: TWSE={dates_twse}, TPEx={dates_tpex}")
        if dates_twse == dates_tpex:
            return twse, tpex, next(iter(dates_twse))
        message = f"Source dates not aligned (attempt {attempt}/{max_attempts}): TWSE={dates_twse}, TPEx={dates_tpex}"
        if attempt == max_attempts:
            raise ValueError(message + "; refusing to publish a mixed-date snapshot")
        print(f"[WARN] {message}; retrying in {wait_seconds}s")
        time.sleep(wait_seconds)
    raise RuntimeError("Unreachable date synchronization state")


def load_history() -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    if not HISTORY.exists(): return grouped
    for path in sorted(HISTORY.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            for row in payload.get("quotes", []):
                grouped.setdefault(row["code"], []).append({"date": payload["date"], "close": row["close"],
                    "high": row.get("high"), "low": row.get("low"), "volume": row.get("volume")})
        except (OSError, ValueError, KeyError, TypeError) as exc:
            print(f"[WARN] skipping unreadable history {path.name}: {exc}")
    return grouped


def main() -> None:
    print("[INFO] collecting official TWSE + TPEx daily closing quotes")
    twse, tpex, trade_date = fetch_aligned_quotes()

    universe = fetch_stock_universe()
    raw_quotes = twse + tpex
    quotes = filter_quotes_by_universe(raw_quotes, universe)
    if len(quotes) < 100:
        raise ValueError(f"Filtered listed/OTC company universe has only {len(quotes)} usable quotes")
    for row in quotes: row.pop("date", None)
    quotes.sort(key=lambda row: row["volume"], reverse=True)
    top100 = quotes[:100]

    valuations = fetch_valuations()
    for row in top100: row.update(valuations.get(row["code"], {}))
    HISTORY.mkdir(parents=True, exist_ok=True)
    snapshot = {"date": trade_date, "source": ["TWSE OpenAPI", "TPEx OpenAPI"],
        "universe_source": ["TWSE listed company master t187ap03_L", "TPEx OTC stock master mopsfin_t187ap03_O"],
        "raw_quote_count": len(raw_quotes), "eligible_quote_count": len(quotes), "quotes": quotes}
    (HISTORY / f"{trade_date}.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    history = load_history()
    for row in top100: row["technical"] = calculate(history.get(row["code"], []))
    payload = {"date": trade_date, "market_data_type": "daily_close",
        "universe_rule": "Official TWSE listed company master + TPEx OTC stock master; daily traded shares descending; top 100",
        "raw_market_quote_count": len(raw_quotes), "eligible_stock_quote_count": len(quotes),
        "top100": top100,
        "notes": ["Universe is restricted to codes present in official listed/OTC company master lists; non-company instruments such as ETFs and warrants are excluded.",
          "Daily closing data, not intraday real-time quotes.",
          "Official TWSE and TPEx source dates must match; mismatched data is retried and never combined.",
          "Technical indicators use locally stored daily snapshots; they remain null until sufficient history exists.",
          "Historical backfill target is 120 trading-day snapshots.",
          "Full financial-statement metrics are not yet integrated; PE/dividend yield/PB are optional enrichment."]}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] date={trade_date}; raw={len(raw_quotes)}; eligible={len(quotes)}; Top100={len(top100)}")


if __name__ == "__main__": main()
