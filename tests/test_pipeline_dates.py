import unittest
from datetime import date

from src.pipeline import fetch_latest_complete_quotes


def market_rows(day):
    listed = [
        {"date": day.isoformat(), "code": f"L{i:04d}", "market": "上市", "volume": 1000}
        for i in range(500)
    ]
    otc = [
        {"date": day.isoformat(), "code": f"O{i:04d}", "market": "上櫃", "volume": 1000}
        for i in range(200)
    ]
    return listed + otc


class LatestCompleteSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.universe = {
            "上市": {f"L{i:04d}" for i in range(500)},
            "上櫃": {f"O{i:04d}" for i in range(200)},
        }

    def test_uses_today_when_both_markets_are_complete(self):
        today = date(2026, 11, 11)
        calls = []

        def day_fetch(session, day):
            calls.append(day)
            return market_rows(day)

        raw, eligible, trade_date = fetch_latest_complete_quotes(
            today=today,
            day_fetch=day_fetch,
            session_factory=lambda: object(),
            universe_fetch=lambda session: self.universe,
        )

        self.assertEqual(trade_date, "2026-11-11")
        self.assertEqual(len(raw), 700)
        self.assertEqual(len(eligible), 700)
        self.assertEqual(calls, [today])

    def test_falls_back_to_previous_complete_trading_day(self):
        today = date(2026, 11, 11)
        previous = date(2026, 11, 10)
        calls = []

        def day_fetch(session, day):
            calls.append(day)
            if day == today:
                raise ValueError("today's official data is not published yet")
            return market_rows(day)

        _, eligible, trade_date = fetch_latest_complete_quotes(
            today=today,
            max_lookback_days=2,
            day_fetch=day_fetch,
            session_factory=lambda: object(),
            universe_fetch=lambda session: self.universe,
        )

        self.assertEqual(trade_date, "2026-11-10")
        self.assertEqual(len(eligible), 700)
        self.assertEqual(calls, [today, previous])

    def test_rejects_incomplete_market_coverage_and_uses_earlier_day(self):
        today = date(2026, 11, 11)
        previous = date(2026, 11, 10)

        def day_fetch(session, day):
            rows = market_rows(day)
            if day == today:
                return rows[:600]  # only 100 OTC quotes
            return rows

        _, eligible, trade_date = fetch_latest_complete_quotes(
            today=today,
            max_lookback_days=1,
            day_fetch=day_fetch,
            session_factory=lambda: object(),
            universe_fetch=lambda session: self.universe,
        )

        self.assertEqual(trade_date, "2026-11-10")
        self.assertEqual(len(eligible), 700)

    def test_skips_weekends(self):
        saturday = date(2026, 11, 14)
        friday = date(2026, 11, 13)
        calls = []

        def day_fetch(session, day):
            calls.append(day)
            return market_rows(day)

        _, _, trade_date = fetch_latest_complete_quotes(
            today=saturday,
            max_lookback_days=2,
            day_fetch=day_fetch,
            session_factory=lambda: object(),
            universe_fetch=lambda session: self.universe,
        )

        self.assertEqual(trade_date, friday.isoformat())
        self.assertEqual(calls, [friday])

    def test_fails_if_no_complete_day_is_available(self):
        with self.assertRaisesRegex(RuntimeError, "No complete TWSE\+TPEx snapshot"):
            fetch_latest_complete_quotes(
                today=date(2026, 11, 11),
                max_lookback_days=0,
                day_fetch=lambda session, day: [],
                session_factory=lambda: object(),
                universe_fetch=lambda session: self.universe,
            )


if __name__ == "__main__":
    unittest.main()
