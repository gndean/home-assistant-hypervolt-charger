"""Config flow for Hypervolt EV charger integration."""
from __future__ import annotations

import logging
import aiohttp
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .hypervolt_api_client import HypervoltApiClient, InvalidAuth, CannotConnect
from .const import DOMAIN, CONF_PASSWORD, CONF_USERNAME

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class NoChargersFound(HomeAssistantError):
    """Error to indicate no chargers found within account."""


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    api = HypervoltApiClient(data[CONF_USERNAME], data[CONF_PASSWORD])
    async with aiohttp.ClientSession() as session:
        await api.login(session)
        chargers = await api.get_chargers(session)
        _LOGGER.info("Found chargers: %s", chargers)

        # TODO handle more than one charger
        # Using multi-step config flow? https://developers.home-assistant.io/docs/data_entry_flow_index/#multi-step-flows
        charger_count = len(chargers)
        if charger_count == 0:
            raise NoChargersFound

        if charger_count > 1:
            _LOGGER.warning(
                "%d chargers found but integration only supports one. Selecting just one",
                charger_count,
            )

        charger0_id = str(chargers[0]["charger_id"])

        # Store this in our config
        return {"charger_id": charger0_id}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hypervolt Charger."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except NoChargersFound:
            errors["base"] = "no_chargers_found"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            # Ensure this charger is unique
            await self.async_set_unique_id(info["charger_id"])
            self._abort_if_unique_id_configured()

            # Store charger ID into config
            user_input["charger_id"] = info["charger_id"]

            return self.async_create_entry(title=info["charger_id"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
