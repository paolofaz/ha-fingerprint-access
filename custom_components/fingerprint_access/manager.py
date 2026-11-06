"""Runtime and persistent authorization database for Fingerprint Access."""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass
from datetime import datetime
import logging
from time import monotonic
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.script import SCRIPT_MODE_SINGLE, Script
from homeassistant.helpers.storage import Store

from .const import (
    CONF_EVENT_PREFIX,
    CONF_FULL_ACTIONS,
    CONF_PARTIAL_ACTIONS,
    DOMAIN,
    ENROLLMENT_TIMEOUT,
    MATCH_COOLDOWN_SECONDS,
    POST_ENROLLMENT_HOLDOFF_SECONDS,
    EVENT_ACCESS,
    PROFILE_FULL,
    STORAGE_VERSION,
    SUFFIX_DONE,
    SUFFIX_FAILED,
    SUFFIX_MATCH,
    SUFFIX_SCAN,
)
from .policy import cooldown_active, lookup_person, parse_slot, validate_person

_LOGGER = logging.getLogger(__name__)


@dataclass
class PendingEnrollment:
    """Pending enrollment, never an authorization until confirmed."""

    slot: int
    name: str
    profile: str


class FingerprintManager:
    """Own one reader's register and its event subscriptions."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.prefix: str = entry.data[CONF_EVENT_PREFIX]
        self.people: dict[str, dict[str, str]] = {}
        self._store = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}")
        self._write_lock = asyncio.Lock()
        self._action_lock = asyncio.Lock()
        self._enrollment_lock = asyncio.Lock()
        self._last_dispatched = 0.0
        self._post_enrollment_holdoff_until = 0.0
        self._recent_events = deque(maxlen=6)
        self.pending: PendingEnrollment | None = None
        self._cancel_timeout = None
        self.last_scan: dict[str, Any] = {}
        # Diagnostic only: counts recognition events since this HA entry was loaded.
        self._matched_count = 0

    @property
    def signal(self) -> str:
        """Dispatcher signal for the summary sensor."""
        return f"{DOMAIN}_{self.entry.entry_id}_updated"

    @property
    def people_list(self) -> list[dict[str, Any]]:
        """Read-only, sorted representation used for the UI."""
        return [
            {"finger_id": int(slot), **record}
            for slot, record in sorted(self.people.items(), key=lambda item: int(item[0]))
        ]

    async def async_load(self) -> None:
        """Load persistent data. Corrupt data prevents setup (fail closed)."""
        stored = await self._store.async_load()
        if stored is None:
            self.people = {}
            return
        if not isinstance(stored, dict) or not isinstance(stored.get("people"), dict):
            raise HomeAssistantError("Invalid fingerprint authorization database")
        validated = {}
        for key, person in stored["people"].items():
            slot = parse_slot(key)
            if slot is None or str(slot) != key or not isinstance(person, dict):
                raise HomeAssistantError("Invalid fingerprint slot in database")
            try:
                validated[key] = validate_person(person.get("name"), person.get("profile"))
            except ValueError as err:
                raise HomeAssistantError("Invalid fingerprint record") from err
        self.people = validated

    @callback
    def notify(self) -> None:
        """Update summary entity after state changes."""
        async_dispatcher_send(self.hass, self.signal)

    def _status(self, status: str, slot: int | None = None, **kwargs: Any) -> None:
        self.last_scan = {
            "status": status,
            "slot": slot,
            "when": datetime.now().astimezone().isoformat(timespec="milliseconds"),
            "matched_count": self._matched_count,
            **kwargs,
        }
        if status in {
            "denied", "invalid_id", "user_event_ignored", "cooldown_ignored",
            "post_enrollment_ignored",
            "busy_ignored", "action_executed", "action_failed",
            "no_actions_configured", "enrollment_saved", "enrollment_failed",
            "enrollment_timeout", "enrollment_save_failed",
            "enrollment_start_failed", "access_revoked",
        }:
            self._recent_events.appendleft(dict(self.last_scan))
        self.notify()
        self.hass.bus.async_fire(EVENT_ACCESS, {"reader": self.prefix, **self.last_scan})

    async def async_mutate(self, change) -> None:
        """Serialize read/modify/write operations; never resurrect revoked access."""
        async with self._write_lock:
            updated = change(dict(self.people))
            await self._store.async_save({"people": updated})
            self.people = updated
            self.notify()

    def subscribe(self) -> None:
        """Attach event listeners to precisely this reader's event types."""
        for suffix, handler in (
            (SUFFIX_MATCH, self._on_match),
            (SUFFIX_SCAN, self._on_scan),
            (SUFFIX_DONE, self._on_done),
            (SUFFIX_FAILED, self._on_failed),
        ):
            self.entry.async_on_unload(
                self.hass.bus.async_listen(self.prefix + suffix, handler)
            )

    @callback
    def _on_match(self, event: Event) -> None:
        self._matched_count += 1
        # Refuse manual user-authored bus events. This does NOT authenticate
        # the ESPHome origin or stop privileged automations from forging events.
        if event.context.user_id is not None:
            self._status("user_event_ignored", parse_slot(event.data.get("finger_id")))
            return
        self.hass.async_create_task(self.async_handle_match(event))

    async def async_handle_match(self, event: Event) -> None:
        """Authorize only the slot in this single scan event."""
        slot = parse_slot(event.data.get("finger_id"))
        if slot is None:
            self._status("invalid_id")
            return
        if monotonic() < self._post_enrollment_holdoff_until:
            self._status("post_enrollment_ignored", slot)
            return
        if self.pending is not None:
            self._status("blocked_during_enrollment", slot)
            return
        person = lookup_person(self.people, slot)
        if person is None:
            self._status("denied", slot)
            return
        # Ignore overlapping requests: never queue a delayed door unlock.
        if self._action_lock.locked():
            self._status("busy_ignored", slot)
            return

        async with self._action_lock:
            person = lookup_person(self.people, slot)  # Re-check revocation
            if person is None or self.pending is not None:
                self._status("denied", slot)
                return
            profile = person["profile"]
            actions = self.entry.options.get(
                CONF_FULL_ACTIONS if profile == PROFILE_FULL else CONF_PARTIAL_ACTIONS, []
            )
            if not isinstance(actions, list) or not actions:
                self._status("no_actions_configured", slot, profile=profile)
                return

            now = monotonic()
            if cooldown_active(now, self._last_dispatched, MATCH_COOLDOWN_SECONDS):
                self._status("cooldown_ignored", slot, profile=profile)
                return
            self._last_dispatched = now

            sequence = Script(
                self.hass, actions, name=f"Fingerprint Access {profile}",
                domain=DOMAIN, script_mode=SCRIPT_MODE_SINGLE,
            )
            try:
                await sequence.async_run(
                    {"finger_id": slot, "person_name": person["name"], "profile": profile},
                    context=event.context,
                )
            except Exception:
                _LOGGER.exception("Fingerprint access action sequence failed")
                self._status("action_failed", slot, profile=profile)
                return
            # The action was dispatched; hardware opening is not independently confirmed.
            self._status("action_executed", slot, name=person["name"], profile=profile)

    @callback
    def _on_scan(self, event: Event) -> None:
        slot = parse_slot(event.data.get("finger_id"))
        if self.pending is not None and slot == self.pending.slot:
            self._status("enrolling_scan", slot, scan_num=event.data.get("scan_num"))

    @callback
    def _on_done(self, event: Event) -> None:
        self.hass.async_create_task(self.async_handle_done(event))

    async def async_handle_done(self, event: Event) -> None:
        slot = parse_slot(event.data.get("finger_id"))
        async with self._enrollment_lock:
            pending = self.pending
            if pending is None or slot != pending.slot:
                self._status("unexpected_enrollment_done", slot)
                return

            # Keep all scans blocked until the authorization is durable.
            try:
                def add_person(current):
                    if str(slot) in current:
                        raise ServiceValidationError("Slot already authorized")
                    current[str(slot)] = validate_person(pending.name, pending.profile)
                    return current

                await self.async_mutate(add_person)
            except Exception:
                _LOGGER.exception("Enrollment succeeded but registry could not be saved")
                self._status("enrollment_save_failed", slot)
                return
            finally:
                if self.pending is pending:
                    self._clear_pending()
            self._status("enrollment_saved", slot, name=pending.name, profile=pending.profile)

    @callback
    def _on_failed(self, event: Event) -> None:
        self.hass.async_create_task(self.async_handle_failed(event))

    async def async_handle_failed(self, event: Event) -> None:
        slot = parse_slot(event.data.get("finger_id"))
        async with self._enrollment_lock:
            if self.pending is not None and slot == self.pending.slot:
                self._clear_pending()
                self._status("enrollment_failed", slot)

    def _clear_pending(self) -> None:
        if self.pending is not None:
            self._post_enrollment_holdoff_until = (
                monotonic() + POST_ENROLLMENT_HOLDOFF_SECONDS
            )
        self.pending = None
        if self._cancel_timeout is not None:
            self._cancel_timeout()
            self._cancel_timeout = None
        self.notify()

    def _service_name(self, suffix: str) -> tuple[str, str]:
        """Derive ESPHome native actions from a configured event prefix."""
        node = self.prefix.removeprefix("esphome.")
        return "esphome", node + suffix

    async def _call_esphome(self, suffix: str, data: dict[str, Any] | None = None) -> None:
        domain, service_name = self._service_name(suffix)
        if not self.hass.services.has_service(domain, service_name):
            raise ServiceValidationError(
                f"ESPHome action {domain}.{service_name} is missing or the reader is offline"
            )
        await self.hass.services.async_call(
            domain, service_name, data or {}, blocking=True
        )

    async def start_enrollment(
        self, slot: int, name: str, profile: str, scans: int, confirmed: bool
    ) -> None:
        """Start enrollment; only a matching completion + disk write grants access."""
        if not confirmed:
            raise ServiceValidationError("Confirm the physical slot is free first")
        if isinstance(slot, bool) or parse_slot(slot) != slot or not 2 <= scans <= 6:
            raise ServiceValidationError("Invalid slot or scan count")
        try:
            person = validate_person(name, profile)
        except ValueError as err:
            raise ServiceValidationError(str(err)) from err

        async with self._enrollment_lock:
            if self.pending is not None:
                raise ServiceValidationError("An enrollment is already in progress")
            if str(slot) in self.people:
                raise ServiceValidationError("That slot already belongs to a person")
            pending = PendingEnrollment(slot, person["name"], person["profile"])
            self.pending = pending

            @callback
            def timed_out(_now: Any) -> None:
                if self.pending is pending:
                    self._clear_pending()
                    self._status("enrollment_timeout", slot)

            self._cancel_timeout = async_call_later(
                self.hass, ENROLLMENT_TIMEOUT, timed_out
            )
            self._status("enrollment_started", slot, name=pending.name, profile=pending.profile)
            try:
                await self._call_esphome("enroll", {"finger_id": slot, "num_scans": scans})
            except Exception:
                if self.pending is pending:
                    self._clear_pending()
                self._status("enrollment_start_failed", slot)
                raise

    async def cancel_enrollment(self) -> None:
        """Late completion after cancellation can never grant access."""
        async with self._enrollment_lock:
            slot = self.pending.slot if self.pending else None
            self._clear_pending()
            try:
                await self._call_esphome("cancel_enroll")
            except Exception:
                self._status("enrollment_cancel_failed", slot)
                raise
            self._status("enrollment_cancelled", slot)

    async def edit_person(self, slot: int, name: str, profile: str) -> None:
        """Update a known person with an explicit admin operation."""
        try:
            person = validate_person(name, profile)
        except ValueError as err:
            raise ServiceValidationError(str(err)) from err

        def update(current):
            if str(slot) not in current:
                raise ServiceValidationError("Unknown fingerprint slot")
            current[str(slot)] = person
            return current

        await self.async_mutate(update)
        self._status("person_updated", slot, name=person["name"], profile=person["profile"])

    async def delete_person(self, slot: int) -> None:
        """Revoke access on disk BEFORE requesting physical template deletion."""
        def revoke(current):
            if str(slot) not in current:
                raise ServiceValidationError("Slot is not in the register")
            del current[str(slot)]
            return current

        await self.async_mutate(revoke)
        self._status("access_revoked", slot)
        # If hardware is offline the physical template may remain, but cannot open.
        await self._call_esphome("delete", {"finger_id": slot})
        self._status("template_delete_requested", slot)

    async def shutdown(self) -> None:
        """Clear transient state at unload; no pending request survives restart."""
        self._clear_pending()
