"""Regression tests for safe, idempotent Lovelace card registration."""

from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

BASE = Path(__file__).resolve().parents[1] / "custom_components" / "fingerprint_access"
SPEC = importlib.util.spec_from_file_location(
    "fingerprint_access_lovelace_resource_for_test", BASE / "lovelace_resource.py"
)
resource = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(resource)


class FakeResources:
    def __init__(self, items):
        self.items = [dict(item) for item in items]
        self.loaded = False
        self.calls = []

    async def async_get_info(self):
        self.loaded = True
        self.calls.append(("load",))
        return {"resources": len(self.items)}

    def async_items(self):
        assert self.loaded
        return self.items

    async def async_create_item(self, data):
        self.calls.append(("create", dict(data)))
        self.items.append(
            {"id": "new-card", "url": data["url"], "type": data["res_type"]}
        )

    async def async_update_item(self, item_id, data):
        self.calls.append(("update", item_id, dict(data)))
        for item in self.items:
            if item["id"] == item_id:
                item.update(url=data["url"], type=data["res_type"])
                return
        raise AssertionError("Resource not found")


class LovelaceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.unrelated = [
            {"id": "marketplace1", "url": "/local/community/button-card/button-card.js?v=24", "type": "module"},
            {"id": "marketplace2", "url": "/local/community/mushroom/mushroom.js", "type": "module"},
            {"id": "uconnect", "url": "/local/community/uconnect/uconnect.js", "type": "module"},
        ]
        self.fake_lovelace = types.SimpleNamespace(
            LOVELACE_DATA="lovelace-data",
            MODE_STORAGE="storage",
        )
        self.hass_module = types.ModuleType("homeassistant.components")
        self.hass_module.lovelace = self.fake_lovelace

    async def register(self, store, mode="storage"):
        hass = types.SimpleNamespace(data={"lovelace-data": types.SimpleNamespace(
            resource_mode=mode, resources=store,
        )})
        with patch.dict(sys.modules, {"homeassistant.components": self.hass_module}):
            await resource.async_register_lovelace_resource(hass)

    async def test_new_resource_preserves_every_marketplace_entry(self):
        store = FakeResources(self.unrelated)
        await self.register(store)
        self.assertEqual(store.items[:3], self.unrelated)
        self.assertEqual(store.items[-1]["url"], resource.CARD_RESOURCE_URL)
        self.assertEqual(store.items[-1]["type"], "module")

    async def test_idempotent_after_restart(self):
        store = FakeResources(self.unrelated)
        await self.register(store)
        await self.register(store)
        self.assertEqual(len(store.items), 4)
        self.assertEqual([c[0] for c in store.calls].count("create"), 1)

    async def test_old_own_resource_is_updated_without_touching_others(self):
        own = {"id":"fingerprint", "url":resource.CARD_RESOURCE_PATH+"?v=100rc1", "type":"module"}
        store = FakeResources(self.unrelated + [own])
        await self.register(store)
        self.assertEqual(store.items[:3], self.unrelated)
        self.assertEqual(store.items[3]["url"],resource.CARD_RESOURCE_URL)
        self.assertEqual([c[0] for c in store.calls].count("update"), 1)
        self.assertEqual(store.calls[-1][1], "fingerprint")

    async def test_duplicate_fingerprint_entries_not_modified(self):
        own = [
            {"id":"fingerprint-a","url":resource.CARD_RESOURCE_PATH+"?v=100rc1","type":"module"},
            {"id":"fingerprint-b","url":resource.CARD_RESOURCE_PATH+"?v=100rc2","type":"module"},
        ]
        store = FakeResources(self.unrelated+own)
        await self.register(store)
        self.assertEqual(store.items, self.unrelated+own)
        self.assertEqual(len(store.calls), 1)

    async def test_yaml_mode_never_mutates_resources(self):
        store = FakeResources(self.unrelated)
        await self.register(store, mode="yaml")
        self.assertEqual(store.items, self.unrelated)
        self.assertEqual(store.calls, [])

    async def test_no_other_resource_path_is_mistaken_for_ours(self):
        store = FakeResources(self.unrelated + [
            {"id":"other", "url":"/local/community/fingerprint-access-card.js","type":"module"},
            {"id":"other2", "url":"/fingerprint_access/fingerprint-access-card.js.bak","type":"module"},
        ])
        await self.register(store)
        self.assertEqual(store.items[:5], self.unrelated + [
            {"id":"other", "url":"/local/community/fingerprint-access-card.js","type":"module"},
            {"id":"other2", "url":"/fingerprint_access/fingerprint-access-card.js.bak","type":"module"},
        ])


class StaticIntegrationTests(unittest.TestCase):
    def test_registration_deferred_until_homeassistant_started(self):
        init = (BASE / "__init__.py").read_text()
        self.assertIn("EVENT_HOMEASSISTANT_STARTED", init)
        self.assertIn("CoreState.running", init)
        self.assertIn("async_register_lovelace_resource(hass)", init)
        self.assertNotIn("frontend.add_extra_js_url(", init)
        self.assertNotIn("resource_store.async_create_item(", init)

    def test_manifest_and_frontend(self):
        manifest = json.loads((BASE / "manifest.json").read_text())
        self.assertEqual(manifest["version"], "1.0.0rc3")
        self.assertIn("lovelace", manifest["dependencies"])
        self.assertIn("frontend", manifest["dependencies"])
        self.assertIn("http", manifest["dependencies"])
        js = (BASE / "frontend" / "fingerprint-access-card.js").read_text()
        self.assertIn('customElements.define("fingerprint-access-card"', js)


if __name__ == "__main__":
    unittest.main()
