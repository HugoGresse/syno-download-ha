"""Sensors for the Synology Download Station integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfDataRate
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import SdsConfigEntry, SdsCoordinator, SdsData
from .entity import SdsEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class SdsSensorDescription(SensorEntityDescription):
    """Sensor description with value extractors."""

    value_fn: Callable[[SdsData], StateType]
    attributes_fn: Callable[[SdsData], dict[str, Any]] | None = None


def _latest_completed_attributes(data: SdsData) -> dict[str, Any]:
    """Expose when and how big the latest completed download was."""
    latest = data.summary.latest_completed
    if not latest:
        return {}
    completed_time = latest.get("completed_time") or 0
    return {
        "completed_at": (
            datetime.fromtimestamp(completed_time, tz=UTC).isoformat()
            if completed_time
            else None
        ),
        "size": latest.get("size"),
    }


SENSORS: tuple[SdsSensorDescription, ...] = (
    SdsSensorDescription(
        key="download_speed",
        translation_key="download_speed",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
        suggested_unit_of_measurement=UnitOfDataRate.MEGABYTES_PER_SECOND,
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.speed_download,
    ),
    SdsSensorDescription(
        key="upload_speed",
        translation_key="upload_speed",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
        suggested_unit_of_measurement=UnitOfDataRate.MEGABYTES_PER_SECOND,
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.speed_upload,
    ),
    SdsSensorDescription(
        key="active_downloads",
        translation_key="active_downloads",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.summary.downloading,
        attributes_fn=lambda data: {
            "paused": data.summary.paused,
            "seeding": data.summary.seeding,
            "finished": data.summary.finished,
            "error": data.summary.error,
            "total": data.summary.total,
            "latest_completed": data.summary.latest_completed,
            "tasks": data.summary.tasks,
        },
    ),
    SdsSensorDescription(
        key="overall_progress",
        translation_key="overall_progress",
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.summary.progress,
    ),
    SdsSensorDescription(
        key="latest_completed",
        translation_key="latest_completed",
        value_fn=lambda data: (data.summary.latest_completed or {}).get("title"),
        attributes_fn=_latest_completed_attributes,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SdsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors."""
    coordinator = entry.runtime_data
    async_add_entities(SdsSensor(coordinator, description) for description in SENSORS)


class SdsSensor(SdsEntity, SensorEntity):
    """Sensor driven by a description value extractor."""

    entity_description: SdsSensorDescription

    def __init__(
        self, coordinator: SdsCoordinator, description: SdsSensorDescription
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        super().__init__(coordinator, description.key)

    @property
    def native_value(self) -> StateType:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes when the description provides them."""
        if (attributes_fn := self.entity_description.attributes_fn) is None:
            return None
        return attributes_fn(self.coordinator.data)
