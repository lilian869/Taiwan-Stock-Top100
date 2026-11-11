import unittest
from src.backfill import _extract_market_rows, _find_table


class BackfillParserTests(unittest.TestCase):
    def test_twse_multi_table_selects_stock_quote_table(self):
        payload = {"stat": "OK", "tables": [
            {"fields": ["指數", "收盤指數"], "data": [["加權指數", "23000"]]},
            {"fields": ["證券代號", "證券名稱", "成交股數", "成交金額", "開盤價", "最高價", "最低價", "收盤價", "漲跌價差", "成交筆數"],
             "data": [["2330", "台積電", "1,000", "100,000", "99", "102", "98", "101", "+2", "50"]]}
        ]}
        rows = _extract_market_rows(payload, "上市", "2026-11-10")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["code"], "2330")
        self.assertEqual(rows[0]["close"], 101.0)
        self.assertEqual(rows[0]["volume"], 1000)

    def test_tpex_english_and_chinese_fields(self):
        payload = {"stat": "ok", "tables": [
            {"fields": ["代號", "名稱", "成交股數", "成交金額", "開盤", "最高", "最低", "收盤", "漲跌", "成交筆數"],
             "data": [["6488", "環球晶", "12,345", "6,000,000", "480", "490", "475", "485", "+5", "321"]]}
        ]}
        rows = _extract_market_rows(payload, "上櫃", "2026-11-10")
        self.assertEqual(rows[0]["code"], "6488")
        self.assertEqual(rows[0]["market"], "上櫃")
        self.assertEqual(rows[0]["close"], 485.0)


    def test_twse_numbered_fields_data_sections(self):
        payload = {"stat": "OK",
                   "fields9": ["證券代號", "證券名稱", "成交股數", "收盤價"],
                   "data9": [["2330", "台積電", "123,000", "1,500"]]}
        rows = _extract_market_rows(payload, "上市", "2026-11-10")
        self.assertEqual(rows[0]["code"], "2330")
        self.assertEqual(rows[0]["volume"], 123000)

    def test_missing_table_fails_closed(self):
        with self.assertRaises(ValueError):
            _find_table({"stat": "OK", "tables": []})


if __name__ == "__main__":
    unittest.main()
