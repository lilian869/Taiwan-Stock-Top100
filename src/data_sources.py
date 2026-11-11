"""Official TWSE/TPEx daily market-data adapters."""
from __future__ import annotations
import re
import time
from typing import Any
import requests

TWSE_BASE = "https://openapi.twse.com.tw/v1"
TPEX_BASE = "https://www.tpex.org.tw/openapi/v1"
HEADERS = {"User-Agent": "TaiwanStockTop100/1.1 (+personal research tool)", "Accept": "application/json"}

def _number(value: Any) -> float | None:
    if value is None: return None
    text = str(value).strip().replace(",", "").replace("%", "")
    if text in {"", "--", "---", "-", "N/A", "nan", "None"}: return None
    text = re.sub(r"[^0-9.+-]", "", text)
    if text in {"", "+", "-", ".", "+.", "-."}: return None
    try: return float(text)
    except ValueError: return None

def _pick(row: dict, *keys: str) -> Any:
    for key in keys:
        if key in row and row[key] not in (None, ""): return row[key]
    normalized = {str(k).replace(" ", "").replace("\u3000", ""): v for k, v in row.items()}
    for key in keys:
        candidate = key.replace(" ", "").replace("\u3000", "")
        if candidate in normalized and normalized[candidate] not in (None, ""): return normalized[candidate]
    return None

def _get_json(url: str, session: requests.Session | None = None) -> Any:
    client = session or requests.Session()
    response = client.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    content_type = response.headers.get("Content-Type", "")
    if "json" not in content_type.lower() and not response.text.lstrip().startswith(("[", "{")):
        raise ValueError(f"Expected JSON from {url}; got {content_type or 'unknown content type'}")
    payload = response.json()
    if isinstance(payload, dict) and payload.get("stat") not in (None, "OK"):
        raise ValueError(f"Source returned non-OK status: {payload.get('stat')}")
    return payload

def _normalize(row: dict, market: str) -> dict | None:
    code = str(_pick(row, "Code", "證券代號", "代號", "股票代號", "SecuritiesCompanyCode") or "").strip()
    name = str(_pick(row, "Name", "證券名稱", "名稱", "股票名稱", "CompanyName") or "").strip()
    if not code or not code.isdigit() or not name: return None
    volume = _number(_pick(row, "TradeVolume", "成交股數", "成交量", "成交股數(股)"))
    close = _number(_pick(row, "ClosingPrice", "收盤價", "收盤", "收盤價格"))
    if volume is None or close is None or close <= 0: return None
    return {
        "code": code, "name": name, "market": market, "volume": int(volume),
        "value": _number(_pick(row, "TradeValue", "成交金額")),
        "open": _number(_pick(row, "OpeningPrice", "開盤價", "開盤")),
        "high": _number(_pick(row, "HighestPrice", "最高價", "最高")),
        "low": _number(_pick(row, "LowestPrice", "最低價", "最低")),
        "close": close, "change": _number(_pick(row, "Change", "漲跌價差", "漲跌")),
        "transactions": _number(_pick(row, "Transaction", "成交筆數", "成交筆數(筆)")),
    }

def fetch_twse_quotes(session: requests.Session | None = None) -> list[dict]:
    rows = _get_json(f"{TWSE_BASE}/exchangeReport/STOCK_DAY_ALL", session)
    if not isinstance(rows, list): raise ValueError("TWSE STOCK_DAY_ALL did not return a JSON array")
    result = [item for row in rows if isinstance(row, dict) and (item := _normalize(row, "上市"))]
    if not result: raise ValueError("TWSE returned no usable stock quote rows")
    return result

def fetch_tpex_quotes(session: requests.Session | None = None) -> list[dict]:
    rows = _get_json(f"{TPEX_BASE}/tpex_mainboard_daily_close_quotes", session)
    if not isinstance(rows, list): raise ValueError("TPEx daily close endpoint did not return a JSON array")
    result = [item for row in rows if isinstance(row, dict) and (item := _normalize(row, "上櫃"))]
    if not result: raise ValueError("TPEx returned no usable stock quote rows; check source schema")
    return result

def fetch_valuations(session: requests.Session | None = None) -> dict[str, dict]:
    result: dict[str, dict] = {}
    endpoints = [(f"{TWSE_BASE}/exchangeReport/BWIBBU_ALL", "上市"),
                 (f"{TPEX_BASE}/tpex_mainboard_peratio_analysis", "上櫃")]
    for url, market in endpoints:
        try:
            rows = _get_json(url, session)
            if not isinstance(rows, list): continue
            for row in rows:
                if not isinstance(row, dict): continue
                code = str(_pick(row, "Code", "證券代號", "代號", "股票代號") or "").strip()
                if not code: continue
                result[code] = {"market": market,
                    "pe": _number(_pick(row, "PEratio", "本益比", "本益比(倍)", "本益比(元)")),
                    "dividend_yield": _number(_pick(row, "DividendYield", "殖利率(%)", "殖利率")),
                    "pb": _number(_pick(row, "PBratio", "股價淨值比", "股價淨值比(倍)"))}
            time.sleep(0.25)
        except Exception as exc:
            print(f"[WARN] valuation source unavailable ({market}): {exc}")
    return result
