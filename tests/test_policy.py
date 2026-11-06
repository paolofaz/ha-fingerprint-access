"""Dependency-free safety tests for access policy."""

import importlib.util
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1] / "custom_components" / "fingerprint_access" / "policy.py"
spec = importlib.util.spec_from_file_location("fingerprint_policy", PATH)
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


class PolicyTests(unittest.TestCase):
    def test_valid_slot(self):
        self.assertEqual(policy.parse_slot(20), 20)
        self.assertEqual(policy.parse_slot("20"), 20)

    def test_reject_invalid_slot(self):
        for value in (None, True, -1, 0, 200, 2.0, "2.0", "x", "", "2a"):
            self.assertIsNone(policy.parse_slot(value))

    def test_unknown_denied(self):
        self.assertIsNone(policy.lookup_person({}, 1))
        self.assertIsNone(policy.lookup_person({"1": {"name": "A", "profile": "admin"}}, 1))

    def test_stored_profile(self):
        data = {"1": policy.validate_person(" Alice ", "full")}
        self.assertEqual(policy.lookup_person(data, 1), {"name": "Alice", "profile": "full"})
        self.assertIsNone(policy.lookup_person(data, 2))

    def test_cooldown_and_repeat_scans(self):
        self.assertTrue(policy.cooldown_active(101.0, 100.0, 2.5))
        self.assertFalse(policy.cooldown_active(103.0, 100.0, 2.5))
        self.assertFalse(policy.cooldown_active(100.0, 101.0, 2.5))

    def test_invalid_person(self):
        for name, profile in (("", "full"), ("Alice", "invalid"), (None, "partial")):
            with self.assertRaises(ValueError):
                policy.validate_person(name, profile)


if __name__ == "__main__":
    unittest.main()
