"""Static and policy-independent checks for Lovelace resource registration.

Full integration tests with a real HA instance are still required.
"""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "fingerprint_access"
INIT = COMPONENT / "__init__.py"
CARD = COMPONENT / "frontend" / "fingerprint-access-card.js"
MANIFEST = COMPONENT / "manifest.json"


class LovelaceIntegrationTests(unittest.TestCase):
    def test_real_resource_registration(self):
        source = INIT.read_text(encoding="utf-8")
        self.assertIn("async_register_static_paths(", source)
        self.assertIn("lovelace.LOVELACE_DATA", source)
        self.assertIn("await resource_store.async_get_info()", source)
        self.assertIn("resource_store.async_create_item(", source)
        self.assertIn("resource_store.async_update_item(", source)
        self.assertIn('"res_type": "module"', source)
        self.assertNotIn("frontend.add_extra_js_url(", source)

    def test_manifest_dependencies(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertTrue({"frontend", "lovelace", "http"}.issubset(manifest["dependencies"]))
        self.assertRegex(manifest["version"], r"^\d+\.\d+\.\d+b\d+$")

    def test_card_registration(self):
        source = CARD.read_text(encoding="utf-8")
        self.assertIn('customElements.define("fingerprint-access-card"', source)
        self.assertIn('type:"fingerprint-access-card"', source)
        self.assertIn("static getStubConfig(hass)", source)


if __name__ == "__main__":
    unittest.main()
