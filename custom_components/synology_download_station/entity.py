"""Base entity for the Synology Download Station integration."""

from __future__ import annotations

from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SdsCoordinator


class SdsEntity(CoordinatorEntity[SdsCoordinator]):
    """Entity tied to the Download Station device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SdsCoordinator, key: str) -> None:
        """Initialize unique id and device info."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        protocol = "https" if entry.data[CONF_SSL] else "http"
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Synology Download Station",
            manufacturer="Synology",
            model="Download Station",
            configuration_url=(
                f"{protocol}://{entry.data[CONF_HOST]}:{entry.data[CONF_PORT]}"
            ),
        )
