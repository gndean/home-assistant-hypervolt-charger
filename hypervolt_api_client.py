from __future__ import annotations

import json
import logging
import websockets
import datetime

from homeassistant.exceptions import HomeAssistantError
from .hypervolt_device_state import (
    HypervoltDeviceState,
    HypervoltChargeMode,
    HypervoltLockState,
)

import aiohttp

_LOGGER = logging.getLogger(__name__)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class HypervoltApiClient:
    def __init__(self, username, password, charger_id=None):
        """Set charger_id if known, or None during config, to allow chargers to be enumerated after login()"""
        self.username = username
        self.password = password
        self.charger_id = charger_id

    async def login(self, session: aiohttp.ClientSession):
        """Attempt to log in using credentials from config.
        Raises InvalidAuth or CannotConnect on failure"""

        try:
            async with session.get("https://api.hypervolt.co.uk/login-url") as response:

                login_base_url = json.loads(await response.text())["login"]

                _LOGGER.info("Loading URL: %s", login_base_url)

                # This will cause a 302 redirect to a new URL that loads a login form
                async with session.get(login_base_url) as response:
                    if response.status == 200:
                        login_form_url = response.url
                        state = login_form_url.query["state"]
                        login_form_data = f"state={state}&username={self.username}&password={self.password}&action=default"
                        session.headers.update(
                            {"content-type": "application/x-www-form-urlencoded"}
                        )
                        async with session.post(
                            login_form_url,
                            headers=session.headers,
                            data=login_form_data,
                        ) as response:
                            if response.status == 200:
                                _LOGGER.info("HypervoltApiClient logged in!")
                                return True

                            elif response.status >= 400 and response.status < 500:
                                _LOGGER.error(
                                    "Authentication error when trying to log in, status code: %d",
                                    response.status,
                                )
                                raise InvalidAuth
                            else:
                                response_text = await response.text()
                                _LOGGER.error(
                                    "Error: unable to get charger, status: %d, %s",
                                    response.status,
                                    response_text,
                                )
                                raise CannotConnect
                    else:
                        response_text = await response.text()
                        _LOGGER.error(
                            "Error: unable to login, status: %d, %s",
                            response.status,
                            response_text,
                        )
                        raise InvalidAuth

        except InvalidAuth as exc:
            await session.close()
            raise InvalidAuth from exc
        except Exception as exc:
            await session.close()
            raise CannotConnect from exc

        return session

    async def get_chargers(self, session):
        """Returns an array like: [{"charger_id": 123, "created": "yyyy-MM-ddTHH:mm:ss.sssZ"}]
        Raises InvalidAuth"""
        async with session.get(
            "https://api.hypervolt.co.uk/charger/by-owner"
        ) as response:
            if response.status == 200:
                response_text = await response.text()
                return json.loads(response_text)["chargers"]

            elif response.status >= 400 and response.status < 500:
                _LOGGER.error(
                    "Could not get chargers, status code: %d", response.status
                )
                raise InvalidAuth

    async def get_state(
        self, session: aiohttp.ClientSession, state
    ) -> HypervoltDeviceState:
        """Use API to get the current state. Raise exception on error"""
        if not state:
            state = HypervoltDeviceState()
            state.charger_id = self.charger_id

        async with session.get(
            f"https://api.hypervolt.co.uk/charger/by-id/{self.charger_id}/schedule"
        ) as response:
            if response.status == 200:
                response_text = await response.text()
                print(f"Hypervolt charger schedule: {response_text}")
            elif response.status == 401:
                _LOGGER.warning("Hypervolt get_state charger schedule, unauthorised")
                raise InvalidAuth
            else:
                _LOGGER.error(
                    "Hypervolt get_state charger schedule, error from API, status: %d",
                    response.status,
                )
                raise CannotConnect

        return state

    async def notify_on_hypervolt_sync_push(self, session, on_message_callback):
        """Open websocket to /sync endpoint and notify on updates. This function blocks indefinitely"""

        print(f"notify_on_hypervolt_sync_push enter")

        try:
            # Move cookies from login session to websocket
            requests_cookies = session.cookie_jar.filter_cookies(
                "https://api.hypervolt.co.uk"
            )
            cookies = ""
            for key, cookie in requests_cookies.items():
                cookies += f"{cookie.key}={cookie.value};"

            # TODO: Move this into HypervoltApiClient
            async for websocket in websockets.connect(
                f"wss://api.hypervolt.co.uk/ws/charger/{self.charger_id}/sync",
                extra_headers={"Cookie": cookies},
                origin="https://hypervolt.co.uk",
                host="api.hypervolt.co.uk",
            ):
                try:
                    self.websocket_sync = websocket

                    # Get a snapshot now first
                    await websocket.send('{"id":"0", "method":"sync.snapshot"}')

                    async for message in websocket:
                        print(f"notify_on_hypervolt_sync_push recv {message}")
                        on_message_callback(message)
                except websockets.ConnectionClosed:
                    self.websocket_sync = None
                    continue

        except Exception as exc:
            _LOGGER.error("notify_on_hypervolt_sync_push error: %s", exc)

    async def send_message_to_sync(self, message):
        if self.websocket_sync:
            await self.websocket_sync.send(message)
        else:
            _LOGGER.error(
                "Send_message_to_sync cannot send because websocket_sync is not set"
            )

    async def set_led_brightness(self, value: float):
        """Set the LED brightness, in the range [0.0, 1.0]"""
        message = {
            "id": f"{datetime.datetime.utcnow().timestamp()}",
            "method": "sync.apply",
            "params": {"brightness": value / 100},
        }
        await self.send_message_to_sync(json.dumps(message))

    async def set_charge_mode(self, charge_mode: HypervoltChargeMode):
        """Set the charge mode from the passed in enum class"""
        message = {
            "id": f"{datetime.datetime.utcnow().timestamp()}",
            "method": "sync.apply",
            "params": {"solar_mode": charge_mode.name.lower()},
        }
        await self.send_message_to_sync(json.dumps(message))
