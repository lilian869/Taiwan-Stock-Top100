"""Fail-closed validation for the published Top100 snapshot."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def validate_snapshot(root: Path = ROOT) -> dict:
    latest = json.loads((root / "docs/data/latest.json").read_text(encoding="utf-8"))
    trade_date = latest["date"]
    top100 = latest.get("top100", [])
    if len(top100) != 100:
        raise ValueError(f"Top100 count must be 100; got {len(top100)}")
    codes = [str(row["code"]) for row in top100]
    if len(set(codes)) != 100:
        raise ValueError("Top100 contains duplicate stock codes")

    history_dir = root / "data/history"
    current = json.loads((history_dir / f"{trade_date}.json").read_text(encoding="utf-8"))
    if current.get("date") != trade_date:
        raise ValueError("Current history date does not match latest.json")
    quotes = current.get("quotes", [])
    quote_map = {str(row["code"]): row for row in quotes}
    if len(quote_map) != len(quotes):
        raise ValueError("Current history contains duplicate stock codes")
    if len(quotes) != latest.get("eligible_stock_quote_count"):
        raise ValueError("Current quote count does not match latest.json")

    prior_paths = sorted(p for p in history_dir.glob("*.json")
                         if p.stem < trade_date and len(p.stem) == 10)
    if not prior_paths:
        raise ValueError("No earlier dated snapshot exists")
    prior = json.loads(prior_paths[-1].read_text(encoding="utf-8"))
    prior_map = {str(row["code"]): row for row in prior.get("quotes", [])}
    if prior.get("date") != prior_paths[-1].stem:
        raise ValueError("Prior snapshot filename/date mismatch")

    ranked = sorted(quotes, key=lambda row: int(row["volume"]), reverse=True)[:100]
    if [str(row["code"]) for row in ranked] != codes:
        raise ValueError("Top100 is not the first 100 eligible stocks by traded shares")

    for row in top100:
        code = str(row["code"])
        now, before = quote_map.get(code), prior_map.get(code)
        if now is None:
            raise ValueError(f"{code}: missing current quote")
        if before is None:
            raise ValueError(f"{code}: missing from previous stored snapshot {prior['date']}")
        for field in ("close", "volume"):
            if float(row[field]) != float(now[field]):
                raise ValueError(f"{code}: latest/current {field} mismatch")
        expected = round(float(now["close"]) - float(before["close"]), 4)
        actual = float(row["change"])
        if abs(actual - expected) > 0.0001:
            raise ValueError(f"{code}: change mismatch; published={actual}, expected={expected}, prior_date={prior['date']}")

    result = {"date": trade_date, "prior_date": prior["date"], "top100_checked": 100,
              "eligible_quotes": len(quotes), "volume_ranking": "PASS",
              "close_volume_match": "PASS", "close_to_close_change": "PASS"}
    print("[PASS] Snapshot validation:", json.dumps(result, ensure_ascii=False))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    validate_snapshot(parser.parse_args().root)
