"""Backfill complete-market daily quotes from dated TWSE/TPEx endpoints."""
from __future__ import annotations

import argparse
import json
import re
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests

from src.data_sources import fetch_stock_universe, filter_quotes_by_universe, _number, _iso_date

ROOT = Path(__file__).resolve().parents[1]
HISTORY = ROOT / "data" / "history"
TWSE_URL = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX"
TPEX_URL = "https://www.tpex.org.tw/www/zh-tw/afterTrading/otc"
HEADERS = {"User-Agent": "TaiwanStockTop100/1.1", "Accept": "application/json"}
REQUEST_DELAY = 1.2


def _key(value: Any) -> str:
    return re.sub(r"[\\s\\u3000]", "", str(value or ""))


def _find_table(payload: Any) -> tuple[list[str], list[list[Any]]]:
    """Locate a table by semantic column names, not a brittle table index."""
    if not isinstance(payload, dict):
        raise ValueError("Historical endpoint did not return a JSON object")
    candidates = payload.get("tables")
    if not isinstance(candidates, list):
        candidates = [payload]
    for table in candidates:
        if not isinstance(table, dict):
            continue
        fields = table.get("fields") or table.get("Fields") or []
        rows = table.get("data") or table.get("aaData") or table.get("Data") or []
        normalized = {_key(field) for field in fields}
        has_code = any(x in normalized for x in ("證券代號", "股票代號", "代號", "SecuritiesCompanyCode", "Code"))
        has_close = any(x in normalized for x in ("收盤價", "收盤", "Close", "ClosingPrice"))
        has_volume = any(x in normalized for x in ("成交股數", "成交股數(股)", "成交量", "TradingShares", "TradeVolume"))
        if has_code and has_close and has_volume and isinstance(rows, list):
            return [str(x) for x in fields], rows
    raise ValueError("Could not locate historical quote table with code, close and volume columns")


def _field_index(fields: list[str], *names: str) -> int | None:
    lookup = {_key(name): i for i, name in enumerate(fields)}
    for name in names:
        if _key(name) in lookup:
            return lookup[_key(name)]
    return None


def _at(row: Any, index: int | None) -> Any:
    if index is None:
        return None
    if isinstance(row, (list, tuple)) and index < len(row):
        return row[index]
    if isinstance(row, dict):
        return next((v for k, v in row.items() if _key(k) == str(index)), None)
    return None


def _extract_market_rows(payload: Any, market: str, trade_date: str) -> list[dict]:
    fields, data = _find_table(payload)
    ix = {
        "code": _field_index(fields, "證券代號", "股票代號", "代號", "SecuritiesCompanyCode", "Code"),
        "name": _field_index(fields, "證券名稱", "股票名稱", "名稱", "CompanyName", "Name"),
        "volume": _field_index(fields, "成交股數", "成交股數(股)", "成交量", "TradingShares", "TradeVolume"),
        "value": _field_index(fields, "成交金額", "成交金額(元)", "TradingAmount", "TradeValue"),
        "open": _field_index(fields, "開盤價", "開盤", "Open", "OpeningPrice"),
        "high": _field_index(fields, "最高價", "最高", "High", "HighestPrice"),
        "low": _field_index(fields, "最低價", "最低", "Low", "LowestPrice"),
        "close": _field_index(fields, "收盤價", "收盤", "Close", "ClosingPrice"),
        "change": _field_index(fields, "漲跌價差", "漲跌", "Change"),
        "transactions": _field_index(fields, "成交筆數", "成交筆數(筆)", "Transaction", "TransactionCount"),
    }
    if any(ix[k] is None for k in ("code", "name", "volume", "close")):
        raise ValueError(f"{market} historical quote table is missing required columns: {ix}")
    result = []
    for raw in data:
        code = str(_at(raw, ix["code"]) or "").strip()
        name = str(_at(raw, ix["name"]) or "").strip()
        close = _number(_at(raw, ix["close"]))
        volume = _number(_at(raw, ix["volume"]))
        if not code.isdigit() or not name or close is None or close <= 0 or volume is None:
            continue
        result.append({
            "code": code, "name": name, "market": market, "date": trade_date,
            "volume": int(volume), "value": _number(_at(raw, ix["value"])),
            "open": _number(_at(raw, ix["open"])), "high": _number(_at(raw, ix["high"])),
            "low": _number(_at(raw, ix["low"])), "close": close,
            "change": _number(_at(raw, ix["change"])),
            "transactions": _number(_at(raw, ix["transactions"])),
        })
    if not result:
        raise ValueError(f"{market} historical endpoint returned no usable quote rows for {trade_date}")
    return result


def _get_payload(session: requests.Session, url: str, params: dict) -> Any:
    response = session.get(url, params=params, headers=HEADERS, timeout=40)
    response.raise_for_status()
    if not response.text.lstrip().startswith("{"):
        raise ValueError(f"Historical source returned non-JSON content: {response.url}")
    payload = response.json()
    status = str(payload.get("stat", "OK")).strip().lower() if isinstance(payload, dict) else ""
    if status not in ("ok", ""):
        raise ValueError(f"Historical source status={payload.get('stat')}")
    return payload


def fetch_day(session: requests.Session, day: date) -> list[dict]:
    iso = day.isoformat()
    twse = _get_payload(session, TWSE_URL, {
        "date": day.strftime("%Y%m%d"), "type": "ALLBUT0999", "response": "json"
    })
    time.sleep(REQUEST_DELAY)
    tpex = _get_payload(session, TPEX_URL, {
        "type": "EW", "date": day.strftime("%Y/%m/%d"), "response": "json"
    })
    rows = _extract_market_rows(twse, "上市", iso) + _extract_market_rows(tpex, "上櫃", iso)
    return rows


def _existing_valid_dates() -> set[date]:
    valid = set()
    if not HISTORY.exists():
        return valid
    for path in HISTORY.glob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            parsed = date.fromisoformat(payload["date"])
            quotes = payload.get("quotes", [])
            if isinstance(quotes, list) and len(quotes) >= 100:
                valid.add(parsed)
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return valid


def backfill(target_days: int = 120, max_lookback_days: int = 320) -> int:
    if target_days < 1:
        raise ValueError("target_days must be >= 1")
    HISTORY.mkdir(parents=True, exist_ok=True)
    valid_dates = _existing_valid_dates()
    if len(valid_dates) >= target_days:
        print(f"[OK] history already has {len(valid_dates)} complete snapshots; target={target_days}")
        return len(valid_dates)

    end_date = max(valid_dates) if valid_dates else date.today()
    universe = fetch_stock_universe()
    session = requests.Session()
    added = 0
    failures = 0
    for offset in range(1, max_lookback_days + 1):
        if len(valid_dates) >= target_days:
            break
        day = end_date - timedelta(days=offset)
        if day.weekday() >= 5 or day in valid_dates:
            continue
        try:
            rows = fetch_day(session, day)
            eligible = filter_quotes_by_universe(rows, universe)
            listed_count = sum(row["market"] == "上市" for row in eligible)
            otc_count = sum(row["market"] == "上櫃" for row in eligible)
            if listed_count < 500 or otc_count < 200:
                raise ValueError(f"unexpected market coverage: listed={listed_count}, OTC={otc_count}")
            eligible.sort(key=lambda row: (row["market"], row["code"]))
            snapshot = {
                "date": day.isoformat(),
                "source": ["TWSE dated MI_INDEX", "TPEx dated afterTrading/otc"],
                "universe_source": ["TWSE listed company master", "TPEx OTC stock master"],
                "raw_quote_count": len(rows), "eligible_quote_count": len(eligible),
                "quotes": [{k: v for k, v in row.items() if k != "date"} for row in eligible],
            }
            path = HISTORY / f"{day.isoformat()}.json"
            path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
            valid_dates.add(day)
            added += 1
            print(f"[OK] backfilled {day.isoformat()}: listed={listed_count}, OTC={otc_count}, eligible={len(eligible)}")
        except Exception as exc:
            failures += 1
            print(f"[WARN] skip {day.isoformat()}: {exc}")
        time.sleep(REQUEST_DELAY)

    print(f"[SUMMARY] valid_days={len(valid_dates)} target={target_days} added={added} skipped_or_failed={failures}")
    if len(valid_dates) < target_days:
        raise RuntimeError(f"Historical backfill incomplete: {len(valid_dates)}/{target_days} trading days")
    return len(valid_dates)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-days", type=int, default=120)
    parser.add_argument("--max-lookback-days", type=int, default=320)
    args = parser.parse_args()
    backfill(args.target_days, args.max_lookback_days)
