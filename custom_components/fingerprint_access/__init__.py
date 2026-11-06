"""Fingerprint Access integration: safe authorization independent of the ESP."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import service as service_helper
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, PROFILE_FULL, PROFILE_PARTIAL
from .manager import FingerprintManager

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor"]


def _runtime(hass: HomeAssistant, call: ServiceCall) -> FingerprintManager:
    managers: dict[str, FingerprintManager] = hass.data.get(DOMAIN, {})
    requested = call.data.get("entry_id")
    if requested:
        if requested not in managers:
            raise ServiceValidationError("Unknown Fingerprint Access entry_id")
        return managers[requested]
    if len(managers) != 1:
        raise ServiceValidationError("Specify entry_id when more than one reader exists")
    return next(iter(managers.values()))


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Register administrator-only actions once for the integration."""
    hass.data.setdefault(DOMAIN, {})
    slot_schema = vol.All(vol.Coerce(int), vol.Range(min=1, max=199))
    profile_schema = vol.In([PROFILE_FULL, PROFILE_PARTIAL])
    entry_schema = {vol.Optional("entry_id"): cv.string}

    async def enroll(call: ServiceCall) -> None:
        await _runtime(hass, call).start_enrollment(
            slot=call.data["finger_id"],
            name=call.data["name"],
            profile=call.data["profile"],
            scans=call.data["num_scans"],
            confirmed=call.data["confirm_free_slot"],
        )

    async def cancel(call: ServiceCall) -> None:
        await _runtime(hass, call).cancel_enrollment()

    async def update(call: ServiceCall) -> None:
        await _runtime(hass, call).edit_person(
            call.data["finger_id"], call.data["name"], call.data["profile"]
        )

    async def delete(call: ServiceCall) -> None:
        await _runtime(hass, call).delete_person(call.data["finger_id"])

    async def list_people(call: ServiceCall) -> dict[str, Any]:
        manager = _runtime(hass, call)
        return {
            "reader": manager.prefix,
            "test_mode": manager.test_mode,
            "people": manager.people_list,
        }

    service_helper.async_register_admin_service(
        hass,
        DOMAIN,
        "enroll",
        enroll,
        schema=vol.Schema({
            **entry_schema,
            vol.Required("finger_id"): slot_schema,
            vol.Required("name"): cv.string,
            vol.Required("profile"): profile_schema,
            vol.Optional("num_scans", default=2): vol.All(
                vol.Coerce(int), vol.Range(min=2, max=6)
            ),
            vol.Required("confirm_free_slot"): cv.boolean,
        }),
    )
    service_helper.async_register_admin_service(
        hass, DOMAIN, "cancel_enrollment", cancel,
        schema=vol.Schema(entry_schema),
    )
    service_helper.async_register_admin_service(
        hass, DOMAIN, "update_person", update,
        schema=vol.Schema({
            **entry_schema,
            vol.Required("finger_id"): slot_schema,
            vol.Required("name"): cv.string,
            vol.Required("profile"): profile_schema,
        }),
    )
    service_helper.async_register_admin_service(
        hass, DOMAIN, "delete_person", delete,
        schema=vol.Schema({**entry_schema, vol.Required("finger_id"): slot_schema}),
    )
    service_helper.async_register_admin_service(
        hass, DOMAIN, "list_people", list_people,
        schema=vol.Schema(entry_schema),
        supports_response=SupportsResponse.ONLY,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Load authorization database before subscribing to scans."""
    manager = FingerprintManager(hass, entry)
    await manager.async_load()
    entry.runtime_data = manager
    hass.data[DOMAIN][entry.entry_id] = manager
    manager.subscribe()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Stop listening to the reader."""
    result = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if result:
        await hass.data[DOMAIN][entry.entry_id].shutdown()
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return result
