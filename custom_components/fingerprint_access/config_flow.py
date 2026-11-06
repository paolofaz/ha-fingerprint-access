"""UI configuration and guided management of Fingerprint Access."""

from __future__ import annotations

import logging
import re
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector

from .const import (
    CONF_EVENT_PREFIX,
    CONF_FULL_ACTIONS,
    CONF_PARTIAL_ACTIONS,
    CONF_TEST_MODE,
    DEFAULT_EVENT_PREFIX,
    DOMAIN,
    PROFILE_FULL,
    PROFILE_PARTIAL,
)

_LOGGER = logging.getLogger(__name__)
PREFIX_PATTERN = re.compile(r"^esphome\.[a-z0-9_]+$")


class FingerprintAccessConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Setup a reader by its ESPHome event prefix."""

    VERSION = 1

    def _prefix_in_use(self, prefix: str, exclude_entry_id: str | None = None) -> bool:
        """Check the currently configured event prefix, not the legacy unique ID."""
        return any(
            entry.entry_id != exclude_entry_id
            and entry.data.get(CONF_EVENT_PREFIX) == prefix
            for entry in self.hass.config_entries.async_entries(DOMAIN)
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Change the ESPHome event prefix without replacing the identity register."""
        entry = self._get_reconfigure_entry()
        errors = {}
        if user_input is not None:
            prefix = user_input[CONF_EVENT_PREFIX].strip()
            if not PREFIX_PATTERN.fullmatch(prefix):
                errors["base"] = "invalid_prefix"
            elif self._prefix_in_use(prefix, exclude_entry_id=entry.entry_id):
                errors["base"] = "already_configured"
            elif (manager := self.hass.data.get(DOMAIN, {}).get(entry.entry_id)) and manager.pending:
                errors["base"] = "enrollment_in_progress"
            else:
                # Existing beta entries use the initial event prefix as their unique
                # ID. Migrate it to the stable config-entry ID so future renames
                # never tie device identity to a mutable event name.
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={CONF_EVENT_PREFIX: prefix},
                    unique_id=entry.entry_id,
                    title=f"Fingerprint Access ({prefix})",
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_EVENT_PREFIX,
                        default=entry.data[CONF_EVENT_PREFIX],
                    ): str
                }
            ),
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors = {}
        if user_input is not None:
            prefix = user_input[CONF_EVENT_PREFIX].strip()
            if not PREFIX_PATTERN.fullmatch(prefix):
                errors["base"] = "invalid_prefix"
            elif self._prefix_in_use(prefix):
                errors["base"] = "already_configured"
            else:
                await self.async_set_unique_id(prefix)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Fingerprint Access ({prefix})",
                    data={CONF_EVENT_PREFIX: prefix},
                )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_EVENT_PREFIX, default=DEFAULT_EVENT_PREFIX): str}
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> FingerprintAccessOptionsFlow:
        """Create the options flow."""
        return FingerprintAccessOptionsFlow()


class FingerprintAccessOptionsFlow(config_entries.OptionsFlowWithReload):
    """Configure access actions and manage enrolled identities."""

    _selected_slot: int | None = None

    @property
    def manager(self):
        """Get the active reader runtime."""
        return self.hass.data[DOMAIN][self.config_entry.entry_id]

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        return self.async_show_menu(
            step_id="init",
            menu_options=["actions", "enroll", "manage", "cancel"],
        )

    async def async_step_actions(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                data={
                    **self.config_entry.options,
                    **user_input,
                    CONF_FULL_ACTIONS: user_input.get(CONF_FULL_ACTIONS, []),
                    CONF_PARTIAL_ACTIONS: user_input.get(CONF_PARTIAL_ACTIONS, []),
                }
            )
        current = self.config_entry.options
        return self.async_show_form(
            step_id="actions",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_TEST_MODE, default=current.get(CONF_TEST_MODE, True)
                    ): bool,
                    vol.Optional(
                        CONF_FULL_ACTIONS,
                        default=current.get(CONF_FULL_ACTIONS, []),
                    ): selector.ActionSelector(),
                    vol.Optional(
                        CONF_PARTIAL_ACTIONS,
                        default=current.get(CONF_PARTIAL_ACTIONS, []),
                    ): selector.ActionSelector(),
                }
            ),
        )

    async def async_step_enroll(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors = {}
        if user_input is not None:
            try:
                await self.manager.start_enrollment(
                    slot=user_input["finger_id"],
                    name=user_input["name"],
                    profile=user_input["profile"],
                    scans=user_input["num_scans"],
                    confirmed=user_input["confirm_free_slot"],
                )
            except (HomeAssistantError, ValueError) as err:
                _LOGGER.warning("Cannot begin enrollment: %s", err)
                errors["base"] = "operation_failed"
            else:
                return self.async_abort(reason="enrollment_started")
        return self.async_show_form(
            step_id="enroll",
            data_schema=vol.Schema(
                {
                    vol.Required("finger_id", default=1): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=199)
                    ),
                    vol.Required("name"): str,
                    vol.Required("profile"): vol.In(
                        {PROFILE_FULL: "Accesso completo", PROFILE_PARTIAL: "Accesso parziale"}
                    ),
                    vol.Required("num_scans", default=2): vol.All(
                        vol.Coerce(int), vol.Range(min=2, max=6)
                    ),
                    vol.Required("confirm_free_slot", default=False): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_manage(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if not self.manager.people:
            return self.async_abort(reason="no_people")
        if user_input is not None:
            self._selected_slot = int(user_input["finger_id"])
            return self.async_show_menu(step_id="selected", menu_options=["edit", "remove"])
        choices = {
            str(p["finger_id"]): f'{p["finger_id"]}: {p["name"]} ({p["profile"]})'
            for p in self.manager.people_list
        }
        return self.async_show_form(
            step_id="manage",
            data_schema=vol.Schema({vol.Required("finger_id"): vol.In(choices)}),
        )

    async def async_step_edit(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        slot = self._selected_slot
        if slot is None or str(slot) not in self.manager.people:
            return self.async_abort(reason="no_people")
        original = self.manager.people[str(slot)]
        errors = {}
        if user_input is not None:
            try:
                await self.manager.edit_person(slot, user_input["name"], user_input["profile"])
            except (HomeAssistantError, ValueError) as err:
                _LOGGER.warning("Cannot edit fingerprint person: %s", err)
                errors["base"] = "operation_failed"
            else:
                return self.async_abort(reason="person_updated")
        return self.async_show_form(
            step_id="edit",
            data_schema=vol.Schema(
                {
                    vol.Required("name", default=original["name"]): str,
                    vol.Required("profile", default=original["profile"]): vol.In(
                        {PROFILE_FULL: "Accesso completo", PROFILE_PARTIAL: "Accesso parziale"}
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_remove(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        slot = self._selected_slot
        if slot is None or str(slot) not in self.manager.people:
            return self.async_abort(reason="no_people")
        errors = {}
        if user_input is not None:
            if not user_input["confirm_remove"]:
                errors["base"] = "confirmation_required"
            else:
                try:
                    await self.manager.delete_person(slot)
                except HomeAssistantError as err:
                    _LOGGER.warning("Hardware deletion may have failed after revocation: %s", err)
                    return self.async_abort(reason="deletion_check_hardware")
                return self.async_abort(reason="person_removed")
        return self.async_show_form(
            step_id="remove",
            data_schema=vol.Schema({vol.Required("confirm_remove", default=False): bool}),
            errors=errors,
        )

    async def async_step_cancel(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        try:
            await self.manager.cancel_enrollment()
        except HomeAssistantError:
            return self.async_abort(reason="cancel_failed")
        return self.async_abort(reason="enrollment_cancelled")
