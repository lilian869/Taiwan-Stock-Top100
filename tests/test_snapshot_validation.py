import json
import tempfile
import unittest
from pathlib import Path

from src.validate_snapshot import validate_snapshot


class SnapshotValidationTests(unittest.TestCase):
    def _fixture(self, root: Path, bad_change: bool = False):
        (root / "docs" / "data").mkdir(parents=True)
        (root / "data" / "history").mkdir(parents=True)
        prior_rows = [{"code": str(i), "close": 10.0, "volume": 1000-i} for i in range(100)]
        current_rows = [{"code": str(i), "close": 11.0, "volume": 1000-i} for i in range(100)]
        top = []
        for i, row in enumerate(current_rows):
            top.append({
                "code": row["code"], "close": row["close"], "volume": row["volume"],
                "change": 0.0 if bad_change and i == 0 else 1.0,
            })
        (root / "data" / "history" / "2026-11-13.json").write_text(
            json.dumps({"date": "2026-11-13", "quotes": prior_rows}), encoding="utf-8")
        (root / "data" / "history" / "2026-11-16.json").write_text(
            json.dumps({"date": "2026-11-16", "quotes": current_rows}), encoding="utf-8")
        (root / "docs" / "data" / "latest.json").write_text(
            json.dumps({"date": "2026-11-16", "eligible_stock_quote_count": 100, "top100": top}),
            encoding="utf-8")

    def test_valid_snapshot_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._fixture(root)
            result = validate_snapshot(root)
            self.assertEqual(result["top100_checked"], 100)

    def test_wrong_change_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._fixture(root, bad_change=True)
            with self.assertRaisesRegex(ValueError, "change mismatch"):
                validate_snapshot(root)


if __name__ == "__main__":
    unittest.main()
