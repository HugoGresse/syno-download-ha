"""Serve and register the bundled dashboard card."""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.lovelace import LOVELACE_DATA
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from .const import CARD_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_register_card(hass: HomeAssistant) -> None:
    """Serve card.js and register it with the frontend."""
    card_path = Path(__file__).parent / "frontend" / "card.js"
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(card_path), cache_headers=True)]
    )
    integration = await async_get_integration(hass, DOMAIN)
    versioned_url = f"{CARD_URL}?v={integration.version}"
    add_extra_js_url(hass, versioned_url)
    try:
        await _async_register_resource(hass, versioned_url)
    except Exception:
        _LOGGER.exception(
            "Could not register the dashboard resource automatically; "
            "add %s as a JavaScript module resource manually",
            versioned_url,
        )


async def _async_register_resource(hass: HomeAssistant, versioned_url: str) -> None:
    """Add or update the Lovelace resource entry (storage mode only)."""
    resources = hass.data[LOVELACE_DATA].resources
    if not hasattr(resources, "async_create_item"):
        _LOGGER.debug(
            "Lovelace resources are in YAML mode; add %s manually", versioned_url
        )
        return
    if not resources.loaded:
        await resources.async_load()
        resources.loaded = True
    for item in resources.async_items():
        if item.get("url", "").startswith(CARD_URL):
            if item["url"] != versioned_url:
                await resources.async_update_item(
                    item["id"], {"res_type": "module", "url": versioned_url}
                )
            return
    await resources.async_create_item({"res_type": "module", "url": versioned_url})
