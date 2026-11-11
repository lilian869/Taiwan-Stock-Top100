import unittest
from src.indicators import sma, rsi, macd, stochastic_kd, calculate

class IndicatorTests(unittest.TestCase):
    def test_sma(self):
        self.assertEqual(sma([1, 2, 3, 4, 5], 5), 3)
        self.assertIsNone(sma([1, 2], 5))
    def test_rsi_flat_series(self):
        self.assertEqual(rsi([10] * 20), 50)
    def test_macd_needs_enough_history(self):
        self.assertIsNone(macd([1, 2, 3])["macd"])
    def test_kd_needs_enough_history(self):
        self.assertIsNone(stochastic_kd([2] * 5, [1] * 5, [1.5] * 5)["k"])
    def test_calculate_history_length(self):
        rows = [{"date": f"2026-01-{i:02d}", "close": float(i), "high": float(i+1), "low": float(i-1), "volume": 100} for i in range(1, 31)]
        result = calculate(rows)
        self.assertEqual(result["history_days"], 30)
        self.assertIsNotNone(result["ma20"])

if __name__ == "__main__": unittest.main()
