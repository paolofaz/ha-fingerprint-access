"""Release candidate safety invariants (static checks).

Hardware and Home Assistant runtime tests must still be performed.
"""
from pathlib import Path
import json
import unittest

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "fingerprint_access"

class RCChecks(unittest.TestCase):
    def test_test_mode_removed(self):
        for file in ("manager.py", "config_flow.py", "sensor.py"):
            text = (ROOT / file).read_text(encoding="utf-8")
            self.assertNotIn("CONF_TEST_MODE", text)
            self.assertNotIn("self.test_mode", text)

    def test_manager_controls(self):
        source = (ROOT / "manager.py").read_text(encoding="utf-8")
        for value in (
            "lookup_person(self.people, slot)", "no_actions_configured",
            "MATCH_COOLDOWN_SECONDS", "POST_ENROLLMENT_HOLDOFF_SECONDS",
            "_enrollment_lock", "_action_lock.locked()", "_write_lock",
            "user_event_ignored", "async_mutate",
        ):
            self.assertIn(value, source)

    def test_configurable_profiles(self):
        source = (ROOT / "config_flow.py").read_text(encoding="utf-8")
        self.assertIn("CONF_FULL_ACTIONS", source)
        self.assertIn("CONF_PARTIAL_ACTIONS", source)
        self.assertIn("selector.ActionSelector()", source)

    def test_brand_icon_and_version(self):
        obj = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(obj["version"], "1.0.0rc3")
        self.assertTrue((ROOT / "brand" / "icon.png").read_bytes().startswith(b"\x89PNG\r\n\x1a\n"))

if __name__ == "__main__":
    unittest.main()
