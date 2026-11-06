"""Register only Fingerprint Access's own Lovelace card in storage mode.

Registration is deferred until HA is fully started, after the Marketplace's
startup resource migration, to avoid early concurrent loads of the shared
lovelace_resources collection.

All other Lovelace resources remain untouched. YAML-mode users remain
responsible for their own resource list.
"""

from __future__ import annotations

import logging
from urllib.parse import urlsplit

_LOGGER = logging.getLogger(__name__)

CARD_RESOURCE_PATH = "/fingerprint_access/fingerprint-access-card.js"
CARD_RESOURCE_URL = CARD_RESOURCE_PATH + "?v=100"


def _is_own_resource(item: dict) -> bool:
    """Match only our exact path, never another Marketplace resource."""
    url = item.get("url")
    return isinstance(url, str) and urlsplit(url).path == CARD_RESOURCE_PATH


async def async_register_lovelace_resource(hass) -> None:
    """Create or update exactly one resource, using HA's collection API."""
    from homeassistant.components import lovelace

    ll_data = hass.data.get(lovelace.LOVELACE_DATA)
    if ll_data is None:
        _LOGGER.warning("Lovelace is unavailable; card resource not registered")
        return

    if ll_data.resource_mode != lovelace.MODE_STORAGE:
        _LOGGER.warning(
            "Lovelace resources use YAML mode; add %s as type 'module' manually",
            CARD_RESOURCE_URL,
        )
        return

    store = ll_data.resources
    # Use the collection's supported API, once the HA startup is complete.
    # Never manipulate the .storage file or reset/reload the collection.
    await store.async_get_info()
    matches = [item for item in store.async_items() if _is_own_resource(item)]

    if len(matches) > 1:
        # A pre-existing duplicate is a user-managed conflict. Do not delete
        # anything: duplicates must be examined in dashboard resources.
        _LOGGER.error(
            "Found %d Fingerprint Access resource entries; refusing automatic "
            "changes until duplicates are resolved",
            len(matches),
        )
        return

    if matches:
        current = matches[0]
        if current.get("url") == CARD_RESOURCE_URL and current.get("type") == "module":
            return
        # Only update the exact item ID that matched our own URL path.
        await store.async_update_item(
            current["id"], {"res_type": "module", "url": CARD_RESOURCE_URL}
        )
        _LOGGER.info("Updated Fingerprint Access Lovelace card resource")
        return

    await store.async_create_item(
        {"res_type": "module", "url": CARD_RESOURCE_URL}
    )
    _LOGGER.info("Registered Fingerprint Access Lovelace card resource")
