"""Daily Top 100 collection and static dashboard data generation."""
from __future__ import annotations
import json
from pathlib import Path
from src.data_sources import fetch_twse_quotes, fetch_tpex_quotes, fetch_valuations
from src.indicators import calculate

ROOT = Path(__file__).resolve().parents[1]
HISTORY = ROOT / "data" / "history"
OUTPUT = ROOT / "docs" / "data" / "latest.json"

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
    twse, tpex = fetch_twse_quotes(), fetch_tpex_quotes()
    dates_twse, dates_tpex = {r["date"] for r in twse}, {r["date"] for r in tpex}
    if len(dates_twse) != 1 or len(dates_tpex) != 1:
        raise ValueError(f"Unexpected mixed source dates: TWSE={dates_twse}, TPEx={dates_tpex}")
    if dates_twse != dates_tpex:
        raise ValueError(f"TWSE and TPEx trading dates do not match: {dates_twse} vs {dates_tpex}")
    trade_date = next(iter(dates_twse))
    quotes = twse + tpex
    for row in quotes: row.pop("date", None)
    quotes.sort(key=lambda row: row["volume"], reverse=True)
    top100 = quotes[:100]
    valuations = fetch_valuations()
    for row in top100: row.update(valuations.get(row["code"], {}))
    HISTORY.mkdir(parents=True, exist_ok=True)
    snapshot = {"date": trade_date, "source": ["TWSE OpenAPI", "TPEx OpenAPI"], "quote_count": len(quotes), "quotes": quotes}
    (HISTORY / f"{trade_date}.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    history = load_history()
    for row in top100: row["technical"] = calculate(history.get(row["code"], []))
    payload = {"date": trade_date, "market_data_type": "daily_close",
        "universe_rule": "Combined TWSE listed + TPEx OTC, ranked by daily traded shares",
        "market_quote_count": len(quotes), "top100": top100,
        "notes": ["Daily closing data, not intraday real-time quotes.",
          "Official source dates are compared before writing to avoid duplicate weekend/holiday snapshots.",
          "Technical indicators use locally stored snapshots; they remain null until sufficient history exists.",
          "120-trading-day historical backfill has not yet been performed.",
          "Full financial-statement metrics are not yet integrated; PE/dividend yield/PB are optional enrichment."]}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] date={trade_date}; TWSE={len(twse)}; TPEx={len(tpex)}; total={len(quotes)}; Top100={len(top100)}")

if __name__ == "__main__": main()
