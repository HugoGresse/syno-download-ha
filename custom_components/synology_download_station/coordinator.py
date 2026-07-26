"""DataUpdateCoordinator for Synology Download Station."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from synology_dsm import SynologyDSM
from synology_dsm.exceptions import SynologyDSMException

from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN
from .helpers import DownloadSummary, summarize, task_to_dict

_LOGGER = logging.getLogger(__name__)

type SdsConfigEntry = ConfigEntry[SdsCoordinator]


@dataclass(slots=True)
class SdsData:
    """Data exposed to the entities."""

    summary: DownloadSummary
    speed_download: int
    speed_upload: int


class SdsCoordinator(DataUpdateCoordinator[SdsData]):
    """Poll Download Station tasks and statistics."""

    config_entry: SdsConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: SdsConfigEntry, dsm: SynologyDSM
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )
        self.dsm = dsm

    async def _async_update_data(self) -> SdsData:
        """Fetch tasks and stats, retrying once after a fresh login."""
        try:
            return await self._fetch()
        except SynologyDSMException:
            # The DSM session id expires eventually — one re-login fixes it.
            try:
                await self.dsm.login()
                return await self._fetch()
            except SynologyDSMException as err:
                raise UpdateFailed(f"Download Station update failed: {err}") from err

    async def _fetch(self) -> SdsData:
        download_station = self.dsm.download_station
        await download_station.update()
        stat = await download_station.get_stat() or {}
        stat_data: dict[str, Any] = stat.get("data") or {}
        tasks = [task_to_dict(task) for task in download_station.get_all_tasks()]
        return SdsData(
            summary=summarize(tasks),
            speed_download=stat_data.get("speed_download", 0),
            speed_upload=stat_data.get("speed_upload", 0),
        )

    async def async_add_task(self, url: str, destination: str | None = None) -> None:
        """Create a download task from a magnet/HTTP/FTP/ed2k link."""
        try:
            await self.dsm.download_station.create(
                uri=url.strip(), destination=destination
            )
        except SynologyDSMException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="add_task_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        await self.async_request_refresh()
