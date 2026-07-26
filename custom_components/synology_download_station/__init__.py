"""The Synology Download Station integration."""

from __future__ import annotations

import logging

from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType
from synology_dsm import SynologyDSM
from synology_dsm.exceptions import (
    SynologyDSMException,
    SynologyDSMLoginFailedException,
)

from .const import DOMAIN, PLATFORMS
from .coordinator import SdsConfigEntry, SdsCoordinator
from .resources import async_register_card
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the integration services and the bundled dashboard card."""
    async_setup_services(hass)
    await async_register_card(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: SdsConfigEntry) -> bool:
    """Set up a Download Station from a config entry."""
    session = async_get_clientsession(hass, entry.data[CONF_VERIFY_SSL])
    dsm = SynologyDSM(
        session,
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        use_https=entry.data[CONF_SSL],
    )
    try:
        await dsm.login()
    except SynologyDSMLoginFailedException as err:
        raise ConfigEntryAuthFailed(f"Login failed: {err}") from err
    except SynologyDSMException as err:
        raise ConfigEntryNotReady(
            f"Cannot reach {entry.data[CONF_HOST]}: {err}"
        ) from err

    # The library only requests "detail,file" additionals — "transfer" is
    # what carries size_downloaded and speeds, so override it.
    dsm.download_station.REQUEST_DATA = {"additional": "detail,transfer"}

    coordinator = SdsCoordinator(hass, entry, dsm)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SdsConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        try:
            await entry.runtime_data.dsm.logout()
        except SynologyDSMException as err:
            _LOGGER.debug("Logout failed: %s", err)
    return unload_ok
