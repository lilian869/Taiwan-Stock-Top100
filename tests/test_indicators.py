import unittest
from src.data_sources import _normalize, _iso_date
from src.indicators import sma, rsi, macd, stochastic_kd, calculate

class SourceTests(unittest.TestCase):
    def test_tpex_field_mapping(self):
        row = {"Date":"1151106","SecuritiesCompanyCode":"6488","CompanyName":"環球晶",
               "TradingShares":"123,456","Open":"450","High":"460","Low":"448","Close":"455","Change":"5"}
        parsed = _normalize(row, "上櫃")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["code"], "6488")
        self.assertEqual(parsed["volume"], 123456)
        self.assertEqual(parsed["close"], 455.0)
        self.assertEqual(parsed["date"], "2026-11-06")

    def test_roc_and_gregorian_date(self):
        self.assertEqual(_iso_date("1151106"), "2026-11-06")
        self.assertEqual(_iso_date("20261106"), "2026-11-06")

class IndicatorTests(unittest.TestCase):
    def test_sma(self):
        self.assertEqual(sma([1,2,3,4,5],5),3)
        self.assertIsNone(sma([1,2],5))
    def test_rsi_flat_series(self):
        self.assertEqual(rsi([10]*20),50)
    def test_macd_needs_history(self):
        self.assertIsNone(macd([1,2,3])["macd"])
    def test_kd_needs_history(self):
        self.assertIsNone(stochastic_kd([2]*5,[1]*5,[1.5]*5)["k"])
    def test_calculate_history_length(self):
        rows=[{"date":f"2026-01-{i:02d}","close":float(i),"high":float(i+1),"low":float(i-1),"volume":100} for i in range(1,31)]
        result=calculate(rows)
        self.assertEqual(result["history_days"],30)
        self.assertIsNotNone(result["ma20"])

if __name__ == "__main__": unittest.main()
