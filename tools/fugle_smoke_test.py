"""Read-only Fugle intraday quote smoke test for Taiwan Stock Top100.

Requires FUGLE_API_KEY. Does not write to the repository or publish website data.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parents[1]
LATEST_FILE = ROOT / "docs" / "data" / "latest.json"
API_BASE = "https://api.fugle.tw/marketdata/v1.0/stock"


def load_symbols(path: Path = LATEST_FILE, limit: int | None = None) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("top100")
    if not isinstance(rows, list) or not rows:
        raise ValueError("latest.json does not contain a usable top100 list")
    symbols = []
    for row in rows:
        symbol = str(row.get("code", "")).strip()
        if symbol and symbol not in symbols:
            symbols.append(symbol)
    if limit:
        symbols = symbols[:limit]
    if not symbols:
        raise ValueError("No stock symbols found in latest.json")
    return symbols


def normalize_quote(payload: dict, expected_symbol: str) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("API response is not a JSON object")
    symbol = str(payload.get("symbol", ""))
    if symbol != expected_symbol:
        raise ValueError(f"Symbol mismatch: requested={expected_symbol}, returned={symbol!r}")
    total = payload.get("total") or {}
    volume = total.get("tradeVolume")
    price = payload.get("lastPrice")
    if price is None:
        price = payload.get("closePrice")
    if price is None or volume is None:
        raise ValueError("Missing lastPrice/closePrice or total.tradeVolume")
    return {
        "symbol": symbol,
        "name": payload.get("name"),
        "market": payload.get("market"),
        "price": price,
        "change": payload.get("change"),
        "changePercent": payload.get("changePercent"),
        "tradeVolume": volume,
        "lastUpdated": payload.get("lastUpdated"),
    }


def run_test(symbols: list[str], api_key: str, delay: float = 1.1) -> dict:
    session = requests.Session()
    session.headers.update({"X-API-KEY": api_key, "Accept": "application/json"})
    results = []
    failures = []
    started = time.monotonic()

    for index, symbol in enumerate(symbols, start=1):
        url = f"{API_BASE}/intraday/quote/{symbol}"
        try:
            response = session.get(url, timeout=(10, 20))
            if response.status_code == 429:
                failures.append({"symbol": symbol, "error": "HTTP 429 rate limit; stopped early"})
                print(f"[STOP] HTTP 429 at {symbol}; stopping to protect the free-tier quota.")
                break
            response.raise_for_status()
            row = normalize_quote(response.json(), symbol)
            results.append(row)
            print(
                f"[OK] {index}/{len(symbols)} {symbol} {row['name'] or ''} "
                f"price={row['price']} volume={row['tradeVolume']}"
            )
        except Exception as exc:
            failures.append({"symbol": symbol, "error": f"{type(exc).__name__}: {exc}"})
            print(f"[FAIL] {index}/{len(symbols)} {symbol}: {type(exc).__name__}: {exc}")
            if isinstance(exc, requests.HTTPError) and exc.response is not None and exc.response.status_code in (401, 403):
                print("[STOP] Authentication/permission failure; check the API key and plan.")
                break
        if index < len(symbols):
            time.sleep(max(0.0, delay))

    elapsed = round(time.monotonic() - started, 2)
    summary = {
        "tested_at_taipei": datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds"),
        "requested": len(symbols),
        "success": len(results),
        "failed": len(failures),
        "elapsed_seconds": elapsed,
        "average_seconds_per_request": round(elapsed / max(1, len(results) + len(failures)), 2),
        "results": results,
        "failures": failures,
    }
    print("\n=== Fugle API test summary ===")
    print(json.dumps({k: v for k, v in summary.items() if k not in ("results", "failures")}, ensure_ascii=False, indent=2))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only Fugle API test; no website deployment.")
    parser.add_argument("--all", action="store_true", help="Test all 100 symbols in current latest.json")
    parser.add_argument("--limit", type=int, default=5, help="Number of symbols to test when --all is not set (default: 5)")
    parser.add_argument("--delay", type=float, default=1.1, help="Seconds between requests; default 1.1s for free-tier pacing")
    args = parser.parse_args()

    api_key = os.environ.get("FUGLE_API_KEY", "").strip()
    if not api_key:
        print("[ERROR] FUGLE_API_KEY environment variable is not set. Do not paste the key into source code.")
        return 2
    if args.delay < 1.0:
        print("[ERROR] Delay must be at least 1.0 second to avoid exceeding the published 60/min basic-user limit.")
        return 2

    try:
        symbols = load_symbols(limit=None if args.all else args.limit)
        summary = run_test(symbols, api_key, args.delay)
    except Exception as exc:
        print(f"[ERROR] {type(exc).__name__}: {exc}")
        return 1

    return 0 if summary["success"] == summary["requested"] else 1


if __name__ == "__main__":
    sys.exit(main())
