"""Config flow for Hypervolt EV charger integration."""

from __future__ import annotations

import logging
import aiohttp
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .utils import get_version_from_manifest
from .hypervolt_api_client import HypervoltApiClient, InvalidAuth, CannotConnect
from .const import (
    DOMAIN,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_ENABLE_STALENESS_DETECTION,
)

_LOGGER = logging.getLogger(__name__)

STEP_LOGIN_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def login_and_get_chargers(
    hass: HomeAssistant, data: dict[str, Any]
) -> list[dict[str, Any]]:
    """Log into the HV API and return a list of charger ID strings found within the account"""
    api = HypervoltApiClient(
        await get_version_from_manifest(), data[CONF_USERNAME], data[CONF_PASSWORD]
    )
    async with aiohttp.ClientSession() as session:
        await api.login(session)
        chargers = await api.get_chargers(session)
        _LOGGER.info("Found chargers: %s", chargers)

        return chargers


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hypervolt Charger."""

    def __init__(self):
        self.chargers: list[dict[str, Any]] = []
        self.login_user_input: dict[str, Any] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step. Display form to prompt for login creds"""
        # Show the login form
        return self.async_show_form(step_id="login", data_schema=STEP_LOGIN_SCHEMA)

    async def async_step_login(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle results from the login creds entry"""
        # Store the user input for when we complete the config
        # and create the entry, as there may be more config steps
        self.login_user_input = user_input

        errors = {}

        try:
            self.chargers = await login_and_get_chargers(self.hass, user_input)

            # We support a maximum of 8 chargers per account so truncate the list to that size
            self.chargers = self.chargers[:8]

        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            charger_count = len(self.chargers)
            if charger_count == 0:
                errors["base"] = "no_chargers_found"
            elif charger_count == 1:
                # Complete with this charger
                # Note: this may raise AbortFlow if the ID already exists
                return await self.async_complete_setup(self.chargers[0]["id"])
            else:
                # Allow user to select charger
                # Populate menu options for each of the chargers found
                # The menu ID will trigger a call to async_step_<menu_id> when selected
                charger_menu_options = {}
                for i in range(charger_count):
                    menu_option_text = self.chargers[i].get("model", "")
                    if menu_option_text:
                        menu_option_text += ": "
                    menu_option_text += self.chargers[i].get("id", "<unknown>")
                    charger_menu_options[f"charger_{i}"] = menu_option_text

                return self.async_show_menu(
                    step_id="login", menu_options=charger_menu_options
                )

        # Reshow login form but with errors displayed
        return self.async_show_form(
            step_id="login", data_schema=STEP_LOGIN_SCHEMA, errors=errors
        )

    async def async_complete_setup(self, charger_id: str) -> FlowResult:
        """Complete the setup with the given charger_id
        Raises AbortFlow if the charger_id is already configured"""
        # Ensure this charger is unique
        await self.async_set_unique_id(charger_id)
        self._abort_if_unique_id_configured()

        # Store charger ID into config
        self.login_user_input["charger_id"] = charger_id

        return self.async_create_entry(
            title=f"Hypervolt {charger_id}", data=self.login_user_input
        )

    # Handlers for the selection of the menu options follow
    # We have to create these statically as functions with names corresponding to the menu IDs
    # so its a bit clunky and hopefully we've added enough
    async def async_step_charger_0(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        return await self.async_complete_setup(self.chargers[0]["id"])

    async def async_step_charger_1(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        return await self.async_complete_setup(self.chargers[1]["id"])

    async def async_step_charger_2(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        return await self.async_complete_setup(self.chargers[2]["id"])

    async def async_step_charger_3(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        return await self.async_complete_setup(self.chargers[3]["id"])

    async def async_step_charger_4(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        return await self.async_complete_setup(self.chargers[4]["id"])

    async def async_step_charger_5(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        return await self.async_complete_setup(self.chargers[5]["id"])

    async def async_step_charger_6(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        return await self.async_complete_setup(self.chargers[6]["id"])

    async def async_step_charger_7(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        return await self.async_complete_setup(self.chargers[7]["id"])

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return OptionsFlowHandler()


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Hypervolt Charger."""

    config_entry: config_entries.ConfigEntry

    def __init__(self) -> None:
        """Initialize options flow."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_ENABLE_STALENESS_DETECTION,
                        default=self.config_entry.options.get(
                            CONF_ENABLE_STALENESS_DETECTION, False
                        ),
                    ): bool,
                }
            ),
        )
