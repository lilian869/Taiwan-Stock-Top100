import unittest
from unittest.mock import patch
from src.pipeline import fetch_aligned_quotes


def rows(day):
    return [{"date": day, "code": "2330"}]


class AlignedSourceDateTests(unittest.TestCase):
    def test_retries_until_both_sources_match(self):
        twse_values = iter([rows("2026-11-10"), rows("2026-11-11")])
        tpex_values = iter([rows("2026-11-11"), rows("2026-11-11")])
        with patch("src.pipeline.time.sleep") as sleep:
            twse, tpex, day = fetch_aligned_quotes(
                lambda: next(twse_values), lambda: next(tpex_values),
                max_attempts=2, wait_seconds=3,
            )
        self.assertEqual(day, "2026-11-11")
        self.assertEqual(twse[0]["date"], tpex[0]["date"])
        sleep.assert_called_once_with(3)

    def test_fails_closed_after_mismatch(self):
        with patch("src.pipeline.time.sleep"):
            with self.assertRaisesRegex(ValueError, "refusing to publish"):
                fetch_aligned_quotes(
                    lambda: rows("2026-11-10"), lambda: rows("2026-11-11"),
                    max_attempts=2, wait_seconds=0,
                )

    def test_rejects_mixed_dates_within_one_source(self):
        with self.assertRaisesRegex(ValueError, "Unexpected mixed source dates"):
            fetch_aligned_quotes(
                lambda: rows("2026-11-10") + rows("2026-11-11"),
                lambda: rows("2026-11-10"),
                max_attempts=1, wait_seconds=0,
            )


if __name__ == "__main__":
    unittest.main()
