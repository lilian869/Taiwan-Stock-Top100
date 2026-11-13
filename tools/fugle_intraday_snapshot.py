"""Fetch one read-only Fugle intraday snapshot for the current closing Top 100 universe.

Writes only to a local output path (uploaded as a GitHub Actions artifact by the pilot
workflow). It never commits data or deploys/modifies GitHub Pages.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, time as clock_time
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parents[1]
LATEST_FILE = ROOT / "docs" / "data" / "latest.json"
API_BASE = "https://api.fugle.tw/marketdata/v1.0/stock"
TAIPEI = ZoneInfo("Asia/Taipei")


def load_universe() -> list[dict]:
    payload = json.loads(LATEST_FILE.read_text(encoding="utf-8"))
    rows = payload.get("top100")
    if not isinstance(rows, list) or len(rows) != 100:
        raise ValueError("Expected exactly 100 rows in docs/data/latest.json")
    universe = []
    seen = set()
    for row in rows:
        code = str(row.get("code", "")).strip()
        if code and code not in seen:
            seen.add(code)
            universe.append({"code": code, "name": row.get("name"), "market": row.get("market")})
    if len(universe) != 100:
        raise ValueError(f"Expected 100 unique symbols; found {len(universe)}")
    return universe


def normalize(payload: dict, expected_code: str, base: dict) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("API response is not a JSON object")
    returned = str(payload.get("symbol", ""))
    if returned != expected_code:
        raise ValueError(f"Symbol mismatch: expected {expected_code}, received {returned!r}")
    total = payload.get("total") or {}
    price = payload.get("lastPrice")
    if price is None:
        price = payload.get("closePrice")
    volume = total.get("tradeVolume")
    if price is None or volume is None:
        raise ValueError("Missing price or total.tradeVolume")
    return {
        "code": expected_code,
        "name": payload.get("name") or base.get("name"),
        "market": payload.get("market") or base.get("market"),
        "price": price,
        "change": payload.get("change"),
        "changePercent": payload.get("changePercent"),
        "tradeVolume": volume,
        "lastUpdated": payload.get("lastUpdated"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="artifacts/fugle_intraday_latest.json")
    parser.add_argument("--delay", type=float, default=1.1)
    parser.add_argument("--market-hours-only", action="store_true")
    args = parser.parse_args()

    now = datetime.now(TAIPEI)
    if args.market_hours_only and (now.weekday() >= 5 or not (clock_time(9, 0) <= now.time() <= clock_time(13, 30))):
        print(f"[SKIP] Outside Taiwan market window: {now.isoformat(timespec='seconds')}")
        return 0
    if args.delay < 1.0:
        print("[ERROR] Delay must be at least 1.0 second.")
        return 2
    api_key = os.environ.get("FUGLE_API_KEY", "").strip()
    if not api_key:
        print("[ERROR] FUGLE_API_KEY is not configured.")
        return 2

    universe = load_universe()
    session = requests.Session()
    session.headers.update({"X-API-KEY": api_key, "Accept": "application/json"})
    quotes, failures = [], []
    started = time.monotonic()

    for i, base in enumerate(universe, start=1):
        code = base["code"]
        try:
            response = session.get(f"{API_BASE}/intraday/quote/{code}", timeout=(10, 20))
            if response.status_code == 429:
                failures.append({"code": code, "error": "HTTP 429 rate limit; stopped early"})
                print(f"[STOP] HTTP 429 at {code}; stopping to protect API quota.")
                break
            response.raise_for_status()
            quotes.append(normalize(response.json(), code, base))
            print(f"[OK] {i}/100 {code} price={quotes[-1]['price']} volume={quotes[-1]['tradeVolume']}")
        except Exception as exc:
            failures.append({"code": code, "error": f"{type(exc).__name__}: {exc}"})
            print(f"[FAIL] {i}/100 {code}: {type(exc).__name__}: {exc}")
            if isinstance(exc, requests.HTTPError) and exc.response is not None and exc.response.status_code in (401, 403):
                print("[STOP] Authentication/permission error.")
                break
        if i < len(universe) and len(quotes) + len(failures) < len(universe):
            time.sleep(args.delay)

    completed = datetime.now(TAIPEI)
    result = {
        "asOfTaipei": completed.isoformat(timespec="seconds"),
        "universeDate": json.loads(LATEST_FILE.read_text(encoding="utf-8")).get("date"),
        "source": "Fugle Intraday Quote API",
        "dataType": "intraday_snapshot",
        "requested": len(universe),
        "success": len(quotes),
        "failed": len(failures),
        "elapsedSeconds": round(time.monotonic() - started, 2),
        "quotes": quotes,
        "failures": failures,
        "note": "Intraday tradeVolume may exclude odd-lot, after-hours, and block trades; confirm data redistribution rights before public display."
    }
    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nSUMMARY requested={len(universe)} success={len(quotes)} failed={len(failures)} elapsed={result['elapsedSeconds']}s")
    print(f"SNAPSHOT_FILE={output}")
    return 0 if len(quotes) == len(universe) and not failures else 1


if __name__ == "__main__":
    sys.exit(main())
