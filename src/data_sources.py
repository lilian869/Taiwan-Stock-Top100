"""Official TWSE/TPEx daily market-data adapters."""
from __future__ import annotations
import re
import time
from datetime import date
from typing import Any
import requests

TWSE_BASE = "https://openapi.twse.com.tw/v1"
TPEX_BASE = "https://www.tpex.org.tw/openapi/v1"
HEADERS = {"User-Agent": "TaiwanStockTop100/1.1", "Accept": "application/json"}

def _number(value: Any) -> float | None:
    if value is None: return None
    text = str(value).strip().replace(",", "").replace("%", "")
    if text in {"", "--", "---", "-", "N/A", "nan", "None"}: return None
    text = re.sub(r"[^0-9.+-]", "", text)
    try: return float(text)
    except ValueError: return None

def _pick(row: dict, *keys: str) -> Any:
    for key in keys:
        if key in row and row[key] not in (None, ""): return row[key]
    normalized = {str(k).replace(" ", "").replace("\u3000", ""): v for k, v in row.items()}
    for key in keys:
        key = key.replace(" ", "").replace("\u3000", "")
        if key in normalized and normalized[key] not in (None, ""): return normalized[key]
    return None

def _iso_date(value: Any) -> str | None:
    if value is None: return None
    raw = re.sub(r"[^0-9]", "", str(value).strip())
    if len(raw) == 7:
        return date(int(raw[:3]) + 1911, int(raw[3:5]), int(raw[5:7])).isoformat()
    if len(raw) == 8:
        return date(int(raw[:4]), int(raw[4:6]), int(raw[6:8])).isoformat()
    return None

def _get_json(url: str, session: requests.Session | None = None) -> Any:
    client = session or requests.Session()
    response = client.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    if not response.text.lstrip().startswith(("[", "{")):
        raise ValueError(f"Expected JSON from {url}; received non-JSON response")
    payload = response.json()
    if isinstance(payload, dict) and payload.get("stat") not in (None, "OK"):
        raise ValueError(f"Source returned non-OK status: {payload.get('stat')}")
    return payload

def _normalize(row: dict, market: str) -> dict | None:
    code = str(_pick(row, "Code", "證券代號", "代號", "股票代號", "SecuritiesCompanyCode") or "").strip()
    name = str(_pick(row, "Name", "證券名稱", "名稱", "股票名稱", "CompanyName", "SecuritiesCompanyName") or "").strip()
    if not code or not code.isdigit() or not name: return None
    volume = _number(_pick(row, "TradeVolume", "TradingShares", "成交股數", "成交量", "成交股數(股)"))
    close = _number(_pick(row, "ClosingPrice", "Close", "收盤價", "收盤", "收盤價格"))
    trade_date = _iso_date(_pick(row, "Date", "資料日期", "日期"))
    if volume is None or close is None or close <= 0 or trade_date is None: return None
    return {
        "code": code, "name": name, "market": market, "date": trade_date, "volume": int(volume),
        "value": _number(_pick(row, "TradeValue", "TradingAmount", "成交金額")),
        "open": _number(_pick(row, "OpeningPrice", "Open", "開盤價", "開盤")),
        "high": _number(_pick(row, "HighestPrice", "High", "最高價", "最高")),
        "low": _number(_pick(row, "LowestPrice", "Low", "最低價", "最低")),
        "close": close, "change": _number(_pick(row, "Change", "漲跌價差", "漲跌")),
        "transactions": _number(_pick(row, "Transaction", "TransactionCount", "成交筆數", "成交筆數(筆)")),
    }

def _security_codes(rows: Any, market: str) -> set[str]:
    """Extract official listed/OTC company stock codes; fail closed on schema drift."""
    if not isinstance(rows, list):
        raise ValueError(f"{market} company master did not return a JSON array")
    codes = {
        str(_pick(row, "公司代號", "SecuritiesCompanyCode", "Code") or "").strip()
        for row in rows if isinstance(row, dict)
    }
    codes = {code for code in codes if code.isdigit()}
    if not codes:
        raise ValueError(f"{market} company master returned no usable stock codes")
    return codes

def fetch_stock_universe(session: requests.Session | None = None) -> dict[str, set[str]]:
    """Use official company master lists to exclude ETFs, warrants and other non-company instruments."""
    listed = _get_json(f"{TWSE_BASE}/opendata/t187ap03_L", session)
    otc = _get_json(f"{TPEX_BASE}/mopsfin_t187ap03_O", session)
    return {"上市": _security_codes(listed, "上市"), "上櫃": _security_codes(otc, "上櫃")}

def filter_quotes_by_universe(quotes: list[dict], universe: dict[str, set[str]]) -> list[dict]:
    return [row for row in quotes if row.get("market") in universe and row.get("code") in universe[row["market"]]]

def fetch_twse_quotes(session: requests.Session | None = None) -> list[dict]:
    rows = _get_json(f"{TWSE_BASE}/exchangeReport/STOCK_DAY_ALL", session)
    if not isinstance(rows, list): raise ValueError("TWSE STOCK_DAY_ALL did not return a JSON array")
    result = [item for row in rows if isinstance(row, dict) and (item := _normalize(row, "上市"))]
    if not result: raise ValueError("TWSE returned no usable stock quote rows; verify source schema/date")
    return result

def fetch_tpex_quotes(session: requests.Session | None = None) -> list[dict]:
    rows = _get_json(f"{TPEX_BASE}/tpex_mainboard_daily_close_quotes", session)
    if not isinstance(rows, list): raise ValueError("TPEx daily close endpoint did not return a JSON array")
    result = [item for row in rows if isinstance(row, dict) and (item := _normalize(row, "上櫃"))]
    if not result: raise ValueError("TPEx returned no usable stock quote rows; verify field names and date")
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
                code = str(_pick(row, "Code", "SecuritiesCompanyCode", "證券代號", "代號", "股票代號") or "").strip()
                if not code: continue
                result[code] = {"market": market,
                    "pe": _number(_pick(row, "PEratio", "本益比", "本益比(倍)", "本益比(元)")),
                    "dividend_yield": _number(_pick(row, "DividendYield", "殖利率(%)", "殖利率")),
                    "pb": _number(_pick(row, "PBratio", "股價淨值比", "股價淨值比(倍)"))}
            time.sleep(0.2)
        except Exception as exc:
            print(f"[WARN] valuation source unavailable ({market}): {exc}")
    return result
