"""Guard against inadvertent Lovelace resource storage mutation."""
from pathlib import Path
import json
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "custom_components" / "fingerprint_access"


class LovelaceSafetyTests(unittest.TestCase):
    def test_serves_frontend_without_mutating_resources(self):
        text = (BASE / "__init__.py").read_text()
        self.assertIn("async_register_static_paths(", text)
        self.assertIn('/fingerprint_access/fingerprint-access-card.js', text)
        self.assertNotIn("resource_store.async_create_item(", text)
        self.assertNotIn("resource_store.async_update_item(", text)
        self.assertNotIn("frontend.add_extra_js_url(", text)
        self.assertNotIn("LOVELACE_DATA", text)

    def test_manifest(self):
        info = json.loads((BASE / "manifest.json").read_text())
        self.assertEqual(info["version"], "1.0.0rc2")
        self.assertNotIn("lovelace", info["dependencies"])
        self.assertIn("http", info["dependencies"])

    def test_card_exists(self):
        text = (BASE / "frontend" / "fingerprint-access-card.js").read_text()
        self.assertIn('customElements.define("fingerprint-access-card"', text)


if __name__ == "__main__":
    unittest.main()
