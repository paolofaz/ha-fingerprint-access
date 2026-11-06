"""Isolated behavioral tests of the real manager (mocking Home Assistant I/O).

They simulate service calls and bus events without controlling real hardware.
"""
from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "fingerprint_access"


def module(name, **attributes):
    obj = types.ModuleType(name)
    for key, value in attributes.items():
        setattr(obj, key, value)
    sys.modules[name] = obj
    return obj


class HomeAssistantError(Exception):
    pass


class ServiceValidationError(HomeAssistantError):
    pass


class Event:
    def __init__(self, data, user_id=None):
        self.data = data
        self.context = types.SimpleNamespace(user_id=user_id)


class FakeTemplate:
    """Catch the original bug: Script choose requires Template, not str."""

    def __init__(self, source, hass):
        self.template = source
        self.hass = hass

    def async_render_to_info(self, variables, parse_result=False):
        assert parse_result is False
        expected = "full" if "profile == 'full'" in self.template else "partial"
        return types.SimpleNamespace(
            result=lambda: "true" if variables["profile"] == expected else "false"
        )


class FakeScript:
    calls = []
    instances = []
    hold_runs = False

    def __init__(self, hass, actions, name, domain, script_mode):
        self.actions = actions
        self.mode = script_mode
        self.active_task = None
        self.release = asyncio.Event()
        self.unloaded = False
        self.instances.append(self)

    async def async_run(self, variables, context=None):
        current = asyncio.current_task()
        if self.mode == "restart" and self.active_task and not self.active_task.done():
            previous = self.active_task
            previous.cancel()
            await asyncio.gather(previous, return_exceptions=True)
        self.active_task = current
        # Mock the HA choose action: select the exact configured profile.
        choices = self.actions[0]["choose"]
        matched = [
            choice["sequence"] for choice in choices
            if choice["conditions"][0]["value_template"].async_render_to_info(
                variables, parse_result=False
            ).result() == "true"
        ]
        assert len(matched) == 1
        self.calls.append((matched[0], variables))
        try:
            if self.hold_runs:
                await self.release.wait()
        finally:
            if self.active_task is current:
                self.active_task = None

    async def async_unload(self):
        self.unloaded = True
        if self.active_task and not self.active_task.done():
            self.active_task.cancel()
            await asyncio.gather(self.active_task, return_exceptions=True)



class Store:
    def __init__(self, hass, version, key):
        self.data = None

    async def async_load(self):
        return self.data

    async def async_save(self, data):
        self.data = data


class Bus:
    def __init__(self):
        self.events = []

    def async_fire(self, name, data):
        self.events.append((name, data))

    def async_listen(self, name, handler):
        return lambda: None


class Services:
    def __init__(self):
        self.calls = []

    def has_service(self, domain, name):
        return domain == "esphome"

    async def async_call(self, domain, name, data, blocking):
        self.calls.append((domain, name, data))


class Hass:
    def __init__(self):
        self.bus = Bus()
        self.services = Services()

    def async_create_task(self, coroutine):
        return asyncio.create_task(coroutine)


class Entry:
    data = {"event_prefix": "esphome.impronte3q"}
    entry_id = "test-reader"

    def __init__(self):
        self.options = {
            "full_actions": [{"action": "script.full"}],
            "partial_actions": [{"action": "script.partial"}],
        }

    def async_on_unload(self, callback):
        pass


module("homeassistant")
module("homeassistant.config_entries", ConfigEntry=Entry)
module("homeassistant.core", Event=Event, HomeAssistant=Hass, callback=lambda x: x)
module("homeassistant.exceptions", HomeAssistantError=HomeAssistantError,
       ServiceValidationError=ServiceValidationError)
module("homeassistant.helpers")
module("homeassistant.helpers.dispatcher", async_dispatcher_send=lambda hass, signal: None)
module("homeassistant.helpers.event", async_call_later=lambda hass, seconds, fn: lambda: None)
module("homeassistant.helpers.script", SCRIPT_MODE_RESTART="restart", Script=FakeScript)
module("homeassistant.helpers.storage", Store=Store)
module("homeassistant.helpers.template", Template=FakeTemplate)

package = module("fingerprint_access_rc")
package.__path__ = [str(ROOT)]

for mod in ("const", "policy", "manager"):
    spec = importlib.util.spec_from_file_location(
        f"fingerprint_access_rc.{mod}", ROOT / (mod + ".py")
    )
    loaded = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = loaded
    spec.loader.exec_module(loaded)

manager_module = sys.modules["fingerprint_access_rc.manager"]
FingerManager = manager_module.FingerprintManager


class ManagerTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.hass = Hass()
        self.entry = Entry()
        self.manager = FingerManager(self.hass, self.entry)
        self.clock = 100.0
        manager_module.monotonic = lambda: self.clock
        FakeScript.calls = []
        FakeScript.instances = []
        FakeScript.hold_runs = False

    async def add(self, id, name, profile):
        await self.manager.async_mutate(
            lambda people: {**people, str(id): {"name": name, "profile": profile}}
        )

    async def scan(self, id, user_id=None):
        await self.manager.async_handle_match(Event({"finger_id": id}, user_id=user_id))
        for _ in range(4):
            await asyncio.sleep(0)

    async def asyncTearDown(self):
        await self.manager.shutdown()

    async def test_unknown_id_is_denied(self):
        await self.scan(1)
        self.assertEqual(self.manager.last_scan["status"], "denied")
        self.assertEqual(FakeScript.calls, [])

    async def test_full_and_partial_are_distinct(self):
        await self.add(1, "A", "full")
        await self.add(2, "B", "partial")
        await self.scan(1)
        self.clock += 3
        await self.scan(2)
        self.assertEqual([c[0][0]["action"] for c in FakeScript.calls],
                         ["script.full", "script.partial"])
        self.assertEqual([c[1]["finger_id"] for c in FakeScript.calls], [1, 2])

    async def test_choose_uses_real_template_type_not_string(self):
        """Previously a raw str caused an AttributeError in HA script conditions."""
        await self.add(1, "A", "full")
        await self.scan(1)
        choices = FakeScript.instances[0].actions[0]["choose"]
        for choice in choices:
            template = choice["conditions"][0]["value_template"]
            self.assertIsInstance(template, FakeTemplate)
            self.assertIs(template.hass, self.hass)
            self.assertTrue(hasattr(template, "async_render_to_info"))
        self.assertEqual(self.manager.last_scan["status"], "action_executed")

    async def test_cooldown_at_exactly_one_point_five_seconds(self):
        await self.add(1, "A", "full")
        await self.scan(1)
        self.clock += 1.499
        await self.scan(1)
        self.assertEqual(self.manager.last_scan["status"], "cooldown_ignored")
        self.assertEqual(len(FakeScript.calls), 1)
        self.clock += 0.001
        await self.scan(1)
        self.assertEqual(len(FakeScript.calls), 2)

    async def test_repeat_scan_ignored_during_cooldown(self):
        await self.add(1, "A", "full")
        await self.scan(1)
        self.clock += 1
        await self.scan(1)
        self.assertEqual(self.manager.last_scan["status"], "cooldown_ignored")
        self.assertEqual(len(FakeScript.calls), 1)
        self.clock += 3
        await self.scan(1)
        self.assertEqual(len(FakeScript.calls), 2)

    async def test_restart_after_cooldown_even_with_90_second_action(self):
        """Long running lights cannot lock out another authorized opening."""
        FakeScript.hold_runs = True
        await self.add(1, "A", "full")
        await self.add(2, "B", "partial")
        await self.scan(1)
        self.assertEqual(self.manager.last_scan["status"], "action_started")
        self.assertEqual(len(FakeScript.instances), 1)
        active = FakeScript.instances[0]
        self.assertEqual(active.mode, "restart")
        first_task = active.active_task
        self.assertIsNotNone(first_task)

        self.clock += 1
        await self.scan(2)
        self.assertEqual(self.manager.last_scan["status"], "cooldown_ignored")
        self.assertEqual(len(FakeScript.calls), 1)
        self.assertFalse(first_task.done())

        self.clock += 2
        await self.scan(2)
        self.assertEqual(len(FakeScript.calls), 2)
        self.assertEqual([c[0][0]["action"] for c in FakeScript.calls],
                         ["script.full", "script.partial"])
        self.assertTrue(first_task.done())
        self.assertEqual(self.manager.last_scan["status"], "action_started")
        self.assertEqual(len(FakeScript.instances), 1)  # same restart script
        self.assertIsNot(active.active_task, first_task)

        active.release.set()
        for _ in range(4):
            await asyncio.sleep(0)
        self.assertEqual(self.manager.last_scan["slot"], 2)
        self.assertEqual(self.manager.last_scan["status"], "action_executed")

    async def test_no_match_or_queued_runner_after_unload(self):
        """No queued matched event may resurrect an unloaded integration."""
        await self.add(1, "A", "full")
        self.manager._dispatch_serial = 1
        await self.manager.shutdown()
        await self.scan(1)
        await self.manager._run_action_script(
            1, 1, {"name": "A", "profile": "full"},
            "full", Event({"finger_id": 1}).context,
        )
        self.assertEqual(FakeScript.calls, [])
        self.assertEqual(FakeScript.instances, [])

    async def test_unload_stops_90_second_action(self):
        FakeScript.hold_runs = True
        await self.add(1, "A", "full")
        await self.scan(1)
        active = FakeScript.instances[0]
        self.assertIsNotNone(active.active_task)
        await self.manager.shutdown()
        self.assertTrue(active.unloaded)
        self.assertTrue(active.active_task is None or active.active_task.done())

    async def test_no_actions_never_opens(self):
        await self.add(1, "A", "full")
        self.entry.options["full_actions"] = []
        await self.scan(1)
        self.assertEqual(self.manager.last_scan["status"], "no_actions_configured")
        self.assertEqual(FakeScript.calls, [])

    async def test_enrollment_requires_confirmation_and_matching_done(self):
        await self.manager.start_enrollment(10, "A", "full", 2, True)
        self.assertEqual(self.hass.services.calls[-1][1], "impronte3q_enroll")
        self.assertNotIn("10", self.manager.people)
        await self.manager.async_handle_done(Event({"finger_id": 11}))
        self.assertNotIn("10", self.manager.people)
        await self.manager.async_handle_done(Event({"finger_id": 10}))
        self.assertIn("10", self.manager.people)
        await self.scan(10)
        self.assertEqual(self.manager.last_scan["status"], "post_enrollment_ignored")
        self.clock += 6
        await self.scan(10)
        self.assertEqual(self.manager.last_scan["status"], "action_executed")

    async def test_completed_enrollment_disarms_timeout_before_persistence(self):
        await self.manager.start_enrollment(10, "A", "full", 2, True)
        cancel_called = []
        self.manager._cancel_timeout = lambda: cancel_called.append(True)
        await self.manager.async_handle_done(Event({"finger_id": 10}))
        self.assertEqual(cancel_called, [True])
        self.assertEqual(self.manager.last_scan["status"], "enrollment_saved")
        self.assertIn("10", self.manager.people)

    async def test_cancel_then_late_done_never_authorizes(self):
        await self.manager.start_enrollment(10, "A", "full", 2, True)
        await self.manager.cancel_enrollment()
        self.assertEqual(self.hass.services.calls[-1][1], "impronte3q_cancel_enroll")
        await self.manager.async_handle_done(Event({"finger_id": 10}))
        self.assertNotIn("10", self.manager.people)

    async def test_revocation_before_physical_delete(self):
        await self.add(2, "B", "partial")
        await self.manager.delete_person(2)
        self.assertNotIn("2", self.manager.people)
        self.assertEqual(self.hass.services.calls[-1][1], "impronte3q_delete")
        await self.scan(2)
        self.assertEqual(self.manager.last_scan["status"], "denied")

    async def test_manual_user_event_is_ignored(self):
        await self.add(1, "A", "full")
        self.manager._on_match(Event({"finger_id": 1}, user_id="test-user"))
        self.assertEqual(self.manager.last_scan["status"], "user_event_ignored")
        self.assertEqual(FakeScript.calls, [])


if __name__ == "__main__":
    unittest.main()
