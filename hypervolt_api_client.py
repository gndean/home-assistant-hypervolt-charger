from __future__ import annotations

import json
import logging
import websockets
import datetime
import aiohttp
import asyncio

from homeassistant.exceptions import HomeAssistantError
from .hypervolt_device_state import (
    HypervoltDeviceState,
    HypervoltChargeMode,
    HypervoltLockState,
    HypervoltReleaseState,
    HypervoltActivationMode,
    HypervoltScheduleInterval,
    HypervoltScheduleTime,
)


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

        self.websocket_sync: websockets.client.WebSocketClientProtocol = None
        self.websocket_session_in_progress: websockets.client.WebSocketClientProtocol = (
            None
        )

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

    async def update_state_from_schedule(
        self, session: aiohttp.ClientSession, state: HypervoltDeviceState
    ) -> HypervoltDeviceState:
        """Use API to update the state. Raise exception on error"""

        async with session.get(
            f"https://api.hypervolt.co.uk/charger/by-id/{self.charger_id}/schedule"
        ) as response:
            if response.status == 200:
                response_text = await response.text()
                print(f"Hypervolt charger schedule: {response_text}")

                jres = json.loads(response_text)
                if jres["enabled"]:
                    state.activation_mode = HypervoltActivationMode.SCHEDULE
                else:
                    state.activation_mode = HypervoltActivationMode.PLUG_AND_CHARGE

                state.schedule_intervals = []
                for interval in jres["intervals"]:
                    start = interval[0]
                    end = interval[1]

                    state.schedule_intervals.append(
                        HypervoltScheduleInterval(
                            HypervoltScheduleTime(
                                start["hours"], start["minutes"], start["seconds"]
                            ),
                            HypervoltScheduleTime(
                                end["hours"], end["minutes"], end["seconds"]
                            ),
                        )
                    )

            elif response.status == 401:
                _LOGGER.warning("Update_state_from_schedule, unauthorised")
                raise InvalidAuth
            else:
                _LOGGER.error(
                    "Update_state_from_schedule, error from API, status: %d",
                    response.status,
                )
                raise CannotConnect

        return state

    async def notify_on_hypervolt_sync_push(
        self, session, get_state, on_message_callback
    ):
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
                    _LOGGER.info("Websocket_sync connected")

                    # Get a snapshot now first
                    await self.send_sync_snapshot_request()

                    async for message in websocket:
                        print(
                            f"notify_on_hypervolt_sync_push recv: {message}, task: {asyncio.current_task()}"
                        )

                        try:
                            # Example messages:
                            # {"jsonrpc":"2.0","id":"0","result":[{"brightness":0.25},{"lock_state":"unlocked"},{"release_state":"default"},{"max_current":32000},{"ct_flags":1},{"solar_mode":"boost"},{"features":["super_eco"]},{"random_start":true}]}
                            # or
                            # {"method":"sync.apply","params":[{"brightness":0.25}]}
                            # or
                            # {"jsonrpc":"2.0","id":"1","error":{"code":409,"error":"Concurrent modifications invalidated this request","data":null}}
                            jmsg = json.loads(message)
                            res_array = None
                            if "result" in jmsg:
                                res_array = jmsg["result"]
                            elif "params" in jmsg:
                                res_array = jmsg["params"]

                            state = get_state()

                            if res_array:
                                for item in res_array:
                                    # Only update state if properties are present, other leave state as-is
                                    if "brightness" in item:
                                        state.led_brightness = item["brightness"]
                                    if "lock_state" in item:
                                        state.lock_state = HypervoltLockState[
                                            item["lock_state"].upper()
                                        ]
                                    if "max_current" in item:
                                        state.max_current_milliamps = item[
                                            "max_current"
                                        ]
                                    if "solar_mode" in item:
                                        state.charge_mode = HypervoltChargeMode[
                                            item["solar_mode"].upper()
                                        ]
                                    if "release_state" in item:
                                        state.release_state = HypervoltReleaseState[
                                            item["release_state"].upper()
                                        ]
                                    if "lock_state" in item:
                                        state.release_state = HypervoltLockState[
                                            item["lock_state"].upper()
                                        ]
                                on_message_callback(state)
                            else:
                                _LOGGER.warning(
                                    "notify_on_hypervolt_sync_push unknown message structure: %s",
                                    message,
                                )

                        except Exception as exc:
                            _LOGGER.error(
                                "notify_on_hypervolt_sync_push error: %s",
                                exc,
                            )

                except websockets.ConnectionClosed:
                    self.websocket_sync = None
                    _LOGGER.info("Websocket_sync closed")
                    continue

        except Exception as exc:
            _LOGGER.error("notify_on_hypervolt_sync_push error: %s", exc)

    async def notify_on_hypervolt_session_in_progress_push(
        self, session, get_state, on_message_callback
    ):
        """Open websocket to /session/in-progress endpoint and notify on updates. This function blocks indefinitely"""

        print("notify_on_hypervolt_session_in_progress_push enter")

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
                f"wss://api.hypervolt.co.uk/ws/charger/{self.charger_id}/session/in-progress",
                extra_headers={"Cookie": cookies},
                origin="https://hypervolt.co.uk",
                host="api.hypervolt.co.uk",
            ):
                try:
                    self.websocket_session_in_progress = websocket
                    _LOGGER.info("Websocket_session_in_progress connected")

                    async for message in websocket:
                        print(
                            f"notify_on_hypervolt_session_in_progress_push recv {message}"
                        )

                        try:
                            # Example messages:
                            # {"charging":false,"session":240,"milli_amps":32000,"true_milli_amps":0,"watt_hours":2371,"ccy_spent":34,"carbon_saved_grams":1036,"ct_current":0,"ct_power":0,"voltage":0}

                            jmsg = json.loads(message)
                            state = get_state()

                            # Only update state if properties are present, other leave state as-is
                            if "charging" in jmsg:
                                state.is_charging = jmsg.get("charging")
                            if "session" in jmsg:
                                state.session_id = jmsg["session"]
                            if "watt_hours" in jmsg:
                                state.session_watthours = jmsg["watt_hours"]
                            if "ccy_spent" in jmsg:
                                state.session_currency_spent = jmsg["ccy_spent"]
                            if "carbon_saved_grams" in jmsg:
                                state.session_carbon_saved_grams = jmsg[
                                    "carbon_saved_grams"
                                ]

                            if "true_milli_amps" in jmsg:
                                state.current_session_current_milliamps = jmsg[
                                    "true_milli_amps"
                                ]
                            if "ct_current" in jmsg:
                                state.current_session_ct_current = jmsg["ct_current"]
                            if "ct_power" in jmsg:
                                state.current_session_ct_power = jmsg["ct_power"]
                            if "voltage" in jmsg:
                                state.current_session_voltage = jmsg["voltage"]

                            on_message_callback(state)

                        except Exception as exc:
                            _LOGGER.error(
                                "Notify_on_hypervolt_session_in_progress_push error: %s",
                                exc,
                            )

                except websockets.ConnectionClosed:
                    self.websocket_session_in_progress = None
                    _LOGGER.info("Websocket_session_in_progress closed")
                    continue

        except Exception as exc:
            _LOGGER.error("Notify_on_hypervolt_session_in_progress_push error: %s", exc)

    async def send_message_to_sync(self, message):
        if self.websocket_sync:
            await self.websocket_sync.send(message)
        else:
            _LOGGER.error(
                "Send_message_to_sync cannot send because websocket_sync is not set"
            )

    async def send_sync_snapshot_request(self) -> bool:
        """Ask for a snapshot of the /sync state. Returns true if the sync websocket is ready, false otherwise"""
        if self.websocket_sync:
            message = {
                "id": f"{datetime.datetime.utcnow().timestamp()}",
                "method": "sync.snapshot",
            }
            await self.send_message_to_sync(json.dumps(message))
            return True
        else:
            return False

    async def set_led_brightness(self, value: float):
        """Set the LED brightness, in the range [0.0, 1.0]"""
        message = {
            "id": f"{datetime.datetime.utcnow().timestamp()}",
            "method": "sync.apply",
            "params": {"brightness": value / 100},
        }
        await self.send_message_to_sync(json.dumps(message))

    async def set_max_current_milliamps(self, value: int):
        """Set the Max Current Limit, in the range [6, 32]"""
        message = {
            "id": f"{datetime.datetime.utcnow().timestamp()}",
            "method": "sync.apply",
            "params": {"max_current": value},
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

    async def set_charging(self, charging: bool):
        """Set the charge state"""
        message = {
            "id": f"{datetime.datetime.utcnow().timestamp()}",
            "method": "sync.apply",
            "params": {"release": not charging},
        }
        await self.send_message_to_sync(json.dumps(message))

    async def set_lock_state(self, session: aiohttp.ClientSession, lock: bool):
        """Set the lock state"""

        lock_status_data = {"is_locked": lock}

        async with session.post(
            url=f"https://api.hypervolt.co.uk/charger/by-id/{self.charger_id}/lock-status",
            data=json.dumps(lock_status_data),
            headers={"content-type": "application/json"},
        ) as response:
            if response.status == 200:
                response_text = await response.text()
                print(f"Hypervolt set lock status: {response_text}")
            elif response.status == 401:
                _LOGGER.warning("Set lock status, unauthorised")
                raise InvalidAuth
            else:
                _LOGGER.error(
                    "Set lock status, error from API, status: %d",
                    response.status,
                )
                raise CannotConnect

    async def set_schedule(
        self,
        session: aiohttp.ClientSession,
        activation_mode: HypervoltActivationMode,
        schedule_intervals,
    ) -> HypervoltDeviceState:
        """Use API to update the state. Raise exception on error"""

        schedule_intervals_to_push = []
        for schedule_interval in schedule_intervals:
            schedule_intervals_to_push.append(
                [
                    {
                        "hours": schedule_interval.start_time.hours,
                        "minutes": schedule_interval.start_time.minutes,
                        "seconds": schedule_interval.start_time.seconds,
                    },
                    {
                        "hours": schedule_interval.end_time.hours,
                        "minutes": schedule_interval.end_time.minutes,
                        "seconds": schedule_interval.end_time.seconds,
                    },
                ]
            )

        schedule_data = {
            "type": "restricted",
            "tz": "Europe/London",
            "enabled": activation_mode == HypervoltActivationMode.SCHEDULE,
            "intervals": schedule_intervals_to_push,
        }

        async with session.put(
            url=f"https://api.hypervolt.co.uk/charger/by-id/{self.charger_id}/schedule",
            data=json.dumps(schedule_data),
            headers={"content-type": "application/json"},
        ) as response:
            if response.status == 200:
                response_text = await response.text()
                print(f"Hypervolt charger schedule: {response_text}")
            elif response.status == 401:
                _LOGGER.warning("Set_schedule, unauthorised")
                raise InvalidAuth
            else:
                _LOGGER.error(
                    "Set_schedule, error from API, status: %d",
                    response.status,
                )
                raise CannotConnect
