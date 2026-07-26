"""Text entity used as a submit box to queue a new download."""

from __future__ import annotations

from homeassistant.components.text import TextEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import SdsConfigEntry
from .entity import SdsEntity

PARALLEL_UPDATES = 0

VALID_PREFIXES = (
    "magnet:",
    "http://",
    "https://",
    "ftp://",
    "ftps://",
    "ed2k://",
    "thunder://",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SdsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the add-download text entity."""
    async_add_entities([SdsAddDownloadText(entry.runtime_data)])


class SdsAddDownloadText(SdsEntity, TextEntity):
    """Paste a magnet or torrent URL to start a download.

    The state intentionally stays empty: this is a submit box, not a
    stored value. Note the 255 character state limit — for very long
    magnet links use the add_task action instead.
    """

    _attr_translation_key = "add_download"
    _attr_native_value = ""
    _attr_native_max = 255

    def __init__(self, coordinator) -> None:
        """Initialize the text entity."""
        super().__init__(coordinator, "add_download")

    async def async_set_value(self, value: str) -> None:
        """Queue the pasted link as a new download task."""
        url = value.strip()
        if not url:
            return
        if not url.lower().startswith(VALID_PREFIXES):
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="invalid_url"
            )
        await self.coordinator.async_add_task(url)
        self.async_write_ha_state()
