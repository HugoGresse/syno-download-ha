"""Config flow for the Synology Download Station integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)
from synology_dsm import SynologyDSM
from synology_dsm.exceptions import (
    SynologyDSMException,
    SynologyDSMLogin2SARequiredException,
    SynologyDSMLoginFailedException,
    SynologyDSMRequestException,
)

from .const import (
    CONF_DESTINATION,
    CONF_SCAN_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_USE_SSL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_SSL, default=DEFAULT_USE_SSL): bool,
        vol.Required(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): bool,
        vol.Optional(CONF_DESTINATION): str,
    }
)


async def _async_validate(hass: HomeAssistant, data: dict[str, Any]) -> str | None:
    """Log in and probe Download Station, returning an error key or None."""
    session = async_get_clientsession(hass, data[CONF_VERIFY_SSL])
    dsm = SynologyDSM(
        session,
        data[CONF_HOST],
        data[CONF_PORT],
        data[CONF_USERNAME],
        data[CONF_PASSWORD],
        use_https=data[CONF_SSL],
    )
    try:
        await dsm.login()
        info = await dsm.download_station.get_info()
    except SynologyDSMLogin2SARequiredException:
        return "otp_not_supported"
    except SynologyDSMLoginFailedException:
        return "invalid_auth"
    except SynologyDSMRequestException:
        return "cannot_connect"
    except SynologyDSMException:
        _LOGGER.exception("Unexpected error probing Download Station")
        return "download_station_unavailable"
    if not info:
        return "download_station_unavailable"
    return None


class SdsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(
                f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}".lower()
            )
            self._abort_if_unique_id_configured()
            if (error := await _async_validate(self.hass, user_input)) is None:
                return self.async_create_entry(
                    title=f"Download Station ({user_input[CONF_HOST]})",
                    data=user_input,
                )
            errors["base"] = error
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_SCHEMA, user_input
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> SdsOptionsFlow:
        """Return the options flow."""
        return SdsOptionsFlow()


class SdsOptionsFlow(OptionsFlowWithReload):
    """Handle the options (polling interval)."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the options step."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        entry = self.config_entry
        current_destination = entry.options.get(
            CONF_DESTINATION, entry.data.get(CONF_DESTINATION)
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=entry.options.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=5,
                            max=300,
                            step=1,
                            unit_of_measurement="s",
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Optional(
                        CONF_DESTINATION,
                        description={"suggested_value": current_destination},
                    ): str,
                }
            ),
        )
