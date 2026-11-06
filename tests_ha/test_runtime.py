"""Exercise Fingerprint Access using Home Assistant's real 2026.11 runtime.

No hardware or user configuration is accessed. The test action services are
registered only inside the isolated pytest Home Assistant fixture.
"""
from __future__ import annotations

from homeassistant.core import Context, Event, HomeAssistant
from pytest_homeassistant.common import MockConfigEntry

from custom_components.fingerprint_access.const import (
    CONF_EVENT_PREFIX,
    CONF_FULL_ACTIONS,
    CONF_PARTIAL_ACTIONS,
    DOMAIN,
)
from custom_components.fingerprint_access.manager import FingerprintManager

EVENT_PREFIX = "esphome.test_fingerprint"
FULL = "full"
PARTIAL = "partial"


def _event(slot: int) -> Event:
    return Event(EVENT_PREFIX + "_finger_matched", {"finger_id": slot}, context=Context())


async def test_real_script_choose_authorizes_correct_profile(hass: HomeAssistant) -> None:
    """Execute both configured actions via a real Home Assistant Script.

    RC4 raised AttributeError on a raw string in a template condition.
    This test must reach the registered test services without exceptions.
    """
    calls: list[str] = []

    async def full(_call) -> None:
        calls.append(FULL)

    async def partial(_call) -> None:
        calls.append(PARTIAL)

    hass.services.async_register("fingerprint_runtime_test", FULL, full)
    hass.services.async_register("fingerprint_runtime_test", PARTIAL, partial)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_EVENT_PREFIX: EVENT_PREFIX},
        options={
            CONF_FULL_ACTIONS: [{"action": "fingerprint_runtime_test.full"}],
            CONF_PARTIAL_ACTIONS: [{"action": "fingerprint_runtime_test.partial"}],
        },
    )
    entry.add_to_hass(hass)
    manager = FingerprintManager(hass, entry)
    await manager.async_load()

    try:
        await manager.async_mutate(
            lambda current: {
                **current,
                "1": {"name": "Full tester", "profile": FULL},
                "2": {"name": "Partial tester", "profile": PARTIAL},
            }
        )
        await manager.async_handle_match(_event(1))
        await hass.async_block_till_done()
        assert calls == [FULL]
        assert manager.last_scan["status"] == "action_executed"

        # The global reader cooldown must suppress a second immediate match.
        await manager.async_handle_match(_event(2))
        await hass.async_block_till_done()
        assert calls == [FULL]
        assert manager.last_scan["status"] == "cooldown_ignored"

        # An unknown fingerprint is never dispatched.
        await manager.async_handle_match(_event(199))
        await hass.async_block_till_done()
        assert calls == [FULL]
        assert manager.last_scan["status"] == "denied"

        # Allow the next scan without actually delaying the test.
        manager._last_dispatched -= 2.0
        await manager.async_handle_match(_event(2))
        await hass.async_block_till_done()
        assert calls == [FULL, PARTIAL]
        assert manager.last_scan["status"] == "action_executed"
    finally:
        await manager.shutdown()


async def test_real_storage_survives_manager_reload(hass: HomeAssistant) -> None:
    """The actual Store API keeps the register across manager instances."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_EVENT_PREFIX: EVENT_PREFIX},
        options={CONF_FULL_ACTIONS: [], CONF_PARTIAL_ACTIONS: []},
    )
    entry.add_to_hass(hass)
    first = FingerprintManager(hass, entry)
    await first.async_load()
    await first.async_mutate(
        lambda current: {**current, "12": {"name": "Tester", "profile": PARTIAL}}
    )
    second = FingerprintManager(hass, entry)
    await second.async_load()
    assert second.people_list == [
        {"finger_id": 12, "name": "Tester", "profile": PARTIAL}
    ]
    await first.shutdown()
    await second.shutdown()
