"""Config flow for Hypervolt EV charger integration."""
from __future__ import annotations

import json
import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, CONF_PASSWORD, CONF_USERNAME

_LOGGER = logging.getLogger(__name__)


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    # If your PyPI package is not built with async, pass your methods
    # to the executor:
    # await hass.async_add_executor_job(
    #     your_validate_func, data["username"], data["password"]
    # )

    # SHORTCUT WHILE DEBUGGING
    return {"charger_id": "test1234"}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.hypervolt.co.uk/login-url") as response:

                login_base_url = json.loads(await response.text())["login"]

                print(f"Loading URL: {login_base_url}")

                # This will cause a 302 redirect to a new URL that loads a login form
                async with session.get(login_base_url) as response:
                    if response.status == 200:
                        login_form_url = response.url
                        state = login_form_url.query["state"]
                        login_form_data = f"state={state}&username={data[CONF_USERNAME]}&password={data[CONF_PASSWORD]}&action=default"
                        session.headers.update(
                            {"content-type": "application/x-www-form-urlencoded"}
                        )
                        async with session.post(
                            login_form_url,
                            headers=session.headers,
                            data=login_form_data,
                        ) as response:
                            if response.status == 200:
                                async with session.get(
                                    "https://api.hypervolt.co.uk/charger/by-owner"
                                ) as response:
                                    if response.status == 200:
                                        response_text = await response.text()
                                        chargers = json.loads(response_text)["chargers"]

                                        # TODO handle more than one charger
                                        # Using multi-step config flow? https://developers.home-assistant.io/docs/data_entry_flow_index/#multi-step-flows
                                        # charger_count = len(chargers)
                                        charger0_id = chargers[0]["charger_id"]
                                        # charger0_date_created = chargers[0]["created"]

                                        # Store this in our config
                                        return {"charger_id": charger0_id}

                                    elif (
                                        response.status >= 400 and response.status < 500
                                    ):
                                        print(
                                            f"Could not get chargers, status code: {response.status}"
                                        )
                                        raise InvalidAuth

                                    print(
                                        f"{response.url}, {response.status}, , {response_text}"
                                    )
                            elif response.status >= 400 and response.status < 500:
                                print(
                                    f"Authentication error when trying to log in, status code: {response.status}"
                                )
                                raise InvalidAuth
                            else:
                                response_text = await response.text()
                                print(
                                    f"Error: unable to get charger, status: {response.status}, {response_text}"
                                )
                                raise CannotConnect
                    else:
                        response_text = await response.text()
                        print(
                            f"Error: unable to login, status: {response.status}, {response_text}"
                        )
                        raise CannotConnect

    except InvalidAuth as exc:
        raise InvalidAuth from exc
    except Exception as exc:
        # Assume connection error
        raise CannotConnect from exc


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


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
