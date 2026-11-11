"""Daily Top 100 collection and static dashboard data generation."""
from __future__ import annotations
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from src.data_sources import fetch_twse_quotes, fetch_tpex_quotes, fetch_valuations
from src.indicators import calculate

ROOT = Path(__file__).resolve().parents[1]
DATA, HISTORY = ROOT / "data", ROOT / "data" / "history"
OUTPUT = ROOT / "docs" / "data" / "latest.json"
TZ_TAIPEI = timezone(timedelta(hours=8))

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
    today = datetime.now(TZ_TAIPEI).date().isoformat()
    print(f"[INFO] collecting Taiwan market close snapshot for {today}")
    quotes = fetch_twse_quotes() + fetch_tpex_quotes()
    quotes.sort(key=lambda row: row["volume"], reverse=True)
    top100 = quotes[:100]
    valuations = fetch_valuations()
    for row in top100: row.update(valuations.get(row["code"], {}))
    HISTORY.mkdir(parents=True, exist_ok=True)
    snapshot = {"date": today, "source": ["TWSE OpenAPI", "TPEx OpenAPI"], "quote_count": len(quotes), "quotes": quotes}
    (HISTORY / f"{today}.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    history = load_history()
    for row in top100: row["technical"] = calculate(history.get(row["code"], []))
    payload = {"date": today, "market_data_type": "daily_close",
        "universe_rule": "Combined TWSE listed + TPEx OTC, ranked by daily traded shares",
        "market_quote_count": len(quotes), "top100": top100,
        "notes": ["Daily closing data, not intraday real-time quotes.",
          "Technical indicators use saved daily snapshots; values remain null until sufficient history exists.",
          "120-trading-day historical backfill has not yet been performed.",
          "Full financial-statement metrics are not yet integrated; PE/dividend yield/PB are optional official-source enrichment."]}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] saved {len(quotes)} market quotes; Top 100={len(top100)}; file={OUTPUT}")

if __name__ == "__main__": main()
