"""Regression for repeated scan visibility (static checks).

Home Assistant integration tests are still necessary to validate event ordering.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "fingerprint_access"


class ScanCounterTests(unittest.TestCase):
    def test_count_only_match_events(self):
        manager = (ROOT / "manager.py").read_text(encoding="utf-8")
        self.assertIn("self._matched_count = 0", manager)
        self.assertIn("self._matched_count += 1", manager)
        self.assertIn('"matched_count": self._matched_count', manager)
        self.assertIn('isoformat(timespec="milliseconds")', manager)

    def test_card_displays_timestamp_and_counter(self):
        js = (ROOT / "frontend" / "fingerprint-access-card.js").read_text(encoding="utf-8")
        self.assertIn("last.matched_count", js)
        self.assertIn("last.when", js)
        self.assertIn("Letture riconosciute", js)


if __name__ == "__main__":
    unittest.main()
