"""Services for the Synology Download Station integration."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_DESTINATION,
    ATTR_URL,
    DOMAIN,
    SERVICE_ADD_TASK,
)
from .coordinator import SdsConfigEntry

ADD_TASK_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_URL): cv.string,
        vol.Optional(ATTR_DESTINATION): cv.string,
        vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
    }
)


def _resolve_entry(hass: HomeAssistant, call: ServiceCall) -> SdsConfigEntry:
    """Pick the target config entry for a service call."""
    entries: list[SdsConfigEntry] = hass.config_entries.async_loaded_entries(DOMAIN)
    if entry_id := call.data.get(ATTR_CONFIG_ENTRY_ID):
        for entry in entries:
            if entry.entry_id == entry_id:
                return entry
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="entry_not_found"
        )
    if not entries:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="no_entry_loaded"
        )
    if len(entries) > 1:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="multiple_entries"
        )
    return entries[0]


async def _async_add_task(call: ServiceCall) -> None:
    """Handle the add_task service call."""
    entry = _resolve_entry(call.hass, call)
    await entry.runtime_data.async_add_task(
        call.data[ATTR_URL], call.data.get(ATTR_DESTINATION)
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the integration services."""
    hass.services.async_register(
        DOMAIN, SERVICE_ADD_TASK, _async_add_task, schema=ADD_TASK_SCHEMA
    )
