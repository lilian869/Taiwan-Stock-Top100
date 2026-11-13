import json
import tempfile
import unittest
from pathlib import Path

from tools.fugle_smoke_test import load_symbols, normalize_quote


class FugleSmokeTestUnitTests(unittest.TestCase):
    def test_load_symbols_preserves_leading_zeroes_and_limit(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "latest.json"
            path.write_text(json.dumps({
                "top100": [{"code": "0050"}, {"code": "2330"}, {"code": "0050"}]
            }), encoding="utf-8")
            self.assertEqual(load_symbols(path, limit=2), ["0050", "2330"])

    def test_normalize_quote_maps_price_and_volume(self):
        payload = {
            "symbol": "2330",
            "name": "台積電",
            "market": "TSE",
            "lastPrice": 1500,
            "change": 10,
            "changePercent": 0.67,
            "total": {"tradeVolume": 123456},
            "lastUpdated": 123456789,
        }
        result = normalize_quote(payload, "2330")
        self.assertEqual(result["price"], 1500)
        self.assertEqual(result["tradeVolume"], 123456)

    def test_normalize_quote_rejects_symbol_mismatch(self):
        with self.assertRaises(ValueError):
            normalize_quote({"symbol": "2317", "lastPrice": 100, "total": {"tradeVolume": 10}}, "2330")

    def test_normalize_quote_rejects_missing_volume(self):
        with self.assertRaises(ValueError):
            normalize_quote({"symbol": "2330", "lastPrice": 1500}, "2330")


if __name__ == "__main__":
    unittest.main()
