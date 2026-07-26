"""Services for the Synology Download Station integration."""

from __future__ import annotations

import base64
import binascii
from pathlib import Path

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_DESTINATION,
    ATTR_FILE_PATH,
    ATTR_FILENAME,
    ATTR_TORRENT,
    ATTR_URL,
    DOMAIN,
    SERVICE_ADD_TASK,
    SERVICE_ADD_TORRENT,
)
from .coordinator import SdsConfigEntry

ADD_TASK_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_URL): cv.string,
        vol.Optional(ATTR_DESTINATION): cv.string,
        vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
    }
)

ADD_TORRENT_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Exclusive(ATTR_TORRENT, "source"): cv.string,
            vol.Exclusive(ATTR_FILE_PATH, "source"): cv.string,
            vol.Optional(ATTR_FILENAME): cv.string,
            vol.Optional(ATTR_DESTINATION): cv.string,
            vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
        }
    ),
    cv.has_at_least_one_key(ATTR_TORRENT, ATTR_FILE_PATH),
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


def _decode_torrent(value: str) -> bytes:
    """Decode base64 torrent content, tolerating data-URL prefixes."""
    if value.startswith("data:") and "," in value:
        value = value.split(",", 1)[1]
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="invalid_torrent"
        ) from err


async def _async_add_task(call: ServiceCall) -> None:
    """Handle the add_task service call."""
    entry = _resolve_entry(call.hass, call)
    await entry.runtime_data.async_add_task(
        call.data[ATTR_URL], call.data.get(ATTR_DESTINATION)
    )


async def _async_add_torrent(call: ServiceCall) -> None:
    """Handle the add_torrent service call."""
    entry = _resolve_entry(call.hass, call)
    if file_path := call.data.get(ATTR_FILE_PATH):
        if not call.hass.config.is_allowed_path(file_path):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="path_not_allowed",
                translation_placeholders={"path": file_path},
            )
        path = Path(file_path)
        try:
            content = await call.hass.async_add_executor_job(path.read_bytes)
        except OSError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="file_read_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        filename = call.data.get(ATTR_FILENAME) or path.name
    else:
        content = _decode_torrent(call.data[ATTR_TORRENT])
        filename = call.data.get(ATTR_FILENAME) or "upload.torrent"
    await entry.runtime_data.async_add_torrent(
        content, filename, call.data.get(ATTR_DESTINATION)
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the integration services."""
    hass.services.async_register(
        DOMAIN, SERVICE_ADD_TASK, _async_add_task, schema=ADD_TASK_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_ADD_TORRENT, _async_add_torrent, schema=ADD_TORRENT_SCHEMA
    )
