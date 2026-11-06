"""Read-only registry summary for Fingerprint Access."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .manager import FingerprintManager


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Expose one read-only sensor, never an editable authorization helper."""
    async_add_entities([FingerprintRegistrySensor(entry.runtime_data)])


class FingerprintRegistrySensor(SensorEntity):
    """Number of authorized identities and read-only people list."""

    _attr_has_entity_name = True
    _attr_name = "Registered fingerprints"
    _attr_icon = "mdi:fingerprint"

    def __init__(self, manager: FingerprintManager) -> None:
        self.manager = manager
        self._attr_unique_id = f"{manager.entry.entry_id}_registered"

    @property
    def native_value(self) -> int:
        """Count of registered *authorized* identities, not hardware templates."""
        return len(self.manager.people)

    @property
    def extra_state_attributes(self) -> dict:
        """Expose the register for read-only dashboard rendering."""
        return {
            "reader": self.manager.prefix,
            "entry_id": self.manager.entry.entry_id,
            "people": self.manager.people_list,
            "test_mode": self.manager.test_mode,
            "pending_enrollment": (
                self.manager.pending.slot if self.manager.pending else None
            ),
            "last_scan": self.manager.last_scan,
        }

    async def async_added_to_hass(self) -> None:
        """Subscribe to updates."""
        self.async_on_remove(
            async_dispatcher_connect(self.hass, self.manager.signal, self._changed)
        )

    @callback
    def _changed(self) -> None:
        self.async_write_ha_state()
