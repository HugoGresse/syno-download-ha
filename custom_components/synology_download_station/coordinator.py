"""DataUpdateCoordinator for Synology Download Station."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from aiohttp import ClientError, ClientTimeout, FormData
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from synology_dsm import SynologyDSM
from synology_dsm.exceptions import (
    SynologyDSMAPIErrorException,
    SynologyDSMException,
)

from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN
from .helpers import DownloadSummary, summarize, task_to_dict

_LOGGER = logging.getLogger(__name__)

type SdsConfigEntry = ConfigEntry[SdsCoordinator]

TASK_API_KEY = "SYNO.DownloadStation.Task"
UPLOAD_TIMEOUT = ClientTimeout(total=120)
# Session-expiry codes — one fresh login fixes these.
AUTH_ERROR_CODES = {105, 106, 107, 119}
# "create" error codes from the official Download Station API documentation.
CREATE_ERROR_MESSAGES = {
    400: "File upload failed",
    401: "Maximum number of tasks reached",
    402: "Destination denied",
    403: "Destination does not exist",
    406: "No default destination",
    407: "Setting destination failed",
    408: "File does not exist",
}


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
            summary=summarize(tasks, now=time.time()),
            speed_download=stat_data.get("speed_download", 0),
            speed_upload=stat_data.get("speed_upload", 0),
        )

    async def async_add_task(self, url: str, destination: str | None = None) -> None:
        """Create a download task from a magnet/HTTP/FTP/ed2k link.

        Params are built by hand: the library helper always sends the
        destination key, and None reaches DSM as the string "None", which
        fails with 403 "Destination does not exist".
        """
        params = {"uri": url.strip()}
        if destination:
            params["destination"] = destination
        try:
            await self.dsm.post(TASK_API_KEY, "Create", params)
            await self.dsm.download_station.update()
        except SynologyDSMAPIErrorException as err:
            code = err.args[1] if len(err.args) > 1 else None
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="add_task_failed",
                translation_placeholders={
                    "error": CREATE_ERROR_MESSAGES.get(code, str(err))
                },
            ) from err
        except SynologyDSMException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="add_task_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        await self.async_request_refresh()

    async def async_add_torrent(
        self, content: bytes, filename: str, destination: str | None = None
    ) -> None:
        """Upload a .torrent file and create the download task."""
        try:
            result = await self._post_torrent(content, filename, destination)
            error_code = (result.get("error") or {}).get("code")
            if not result.get("success") and error_code in AUTH_ERROR_CODES:
                await self.dsm.login()
                result = await self._post_torrent(content, filename, destination)
        except (TimeoutError, ValueError, ClientError, SynologyDSMException) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="add_task_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        if not result.get("success"):
            error_code = (result.get("error") or {}).get("code")
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="add_task_failed",
                translation_placeholders={
                    "error": CREATE_ERROR_MESSAGES.get(
                        error_code, f"error code {error_code}"
                    )
                },
            )
        await self.async_request_refresh()

    async def _post_torrent(
        self, content: bytes, filename: str, destination: str | None
    ) -> dict[str, Any]:
        """POST a multipart create request.

        The library only supports multipart uploads for FileStation, so the
        Download Station create-with-file call is built by hand. Private
        _prepare_request resolves endpoint path, API version and session id.
        """
        url, params, _ = await self.dsm._prepare_request(TASK_API_KEY, "create")
        form = FormData(charset="utf-8")
        for key, value in params.items():
            form.add_field(key, str(value))
        if destination:
            form.add_field("destination", destination)
        form.add_field(
            "file",
            content,
            filename=filename,
            content_type="application/octet-stream",
        )
        session = self.dsm._session
        response = await session.post(url, data=form, timeout=UPLOAD_TIMEOUT)
        response.raise_for_status()
        return await response.json(content_type=None)
