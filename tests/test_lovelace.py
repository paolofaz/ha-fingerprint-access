"""Structural regression checks for automatic Lovelace card exposure.

These are static checks; a Home Assistant runtime installation is required to
validate frontend panel/card picker integration end to end.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
INIT = ROOT / "custom_components" / "fingerprint_access" / "__init__.py"
CARD = ROOT / "custom_components" / "fingerprint_access" / "frontend" / "fingerprint-access-card.js"


class LovelaceIntegrationTests(unittest.TestCase):
    def test_frontend_registration(self):
        source = INIT.read_text()
        self.assertIn("frontend.add_extra_js_url(", source)
        self.assertIn("async_register_static_paths(", source)

    def test_card_registration(self):
        source = CARD.read_text()
        self.assertIn('customElements.define("fingerprint-access-card"', source)
        self.assertIn('type:"fingerprint-access-card"', source)
        self.assertIn("static getStubConfig(hass)", source)


if __name__ == "__main__":
    unittest.main()
