import asyncio
import logging
import async_timeout
import aiohttp
import json

from datetime import timedelta
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.update_coordinator import UpdateFailed

from .hypervolt_api_client import HypervoltApiClient
from .hypervolt_device_state import (
    HypervoltDeviceState,
    HypervoltLockState,
    HypervoltChargeMode,
)

from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD, CONF_CHARGER_ID

_LOGGGER = logging.getLogger(__name__)


SCAN_INTERVAL = timedelta(seconds=30)


class HypervoltUpdateCoordinator(DataUpdateCoordinator[HypervoltDeviceState]):
    def __init__(self, hass: HomeAssistant, api: HypervoltApiClient):
        self.api = api

        super().__init__(hass, _LOGGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)

        self.api_session = aiohttp.ClientSession()
        self.websocket_sync: websockets.client.WebSocketClientProtocol = None

    @staticmethod
    async def create_hypervolt_coordinator(
        hass: HomeAssistant, username: str, password: str, charger_id: str
    ) -> "HypervoltUpdateCoordinator":
        # session = async_get_clientsession(hass)
        # TODO: Use this session, to get auto cleanup?
        api = HypervoltApiClient(username, password, charger_id)

        coordinator = HypervoltUpdateCoordinator(hass, api=api)
        await coordinator.async_config_entry_first_refresh()

        if not coordinator.last_update_success:
            raise Exception("Failed to retrieve initial data")

        return coordinator

    @property
    def hypervolt_client(self) -> HypervoltApiClient:
        return self.api

    async def _async_update_data(self):
        try:
            async with async_timeout.timeout(10):
                print("Hypervolt _async_update_data")
                return await self._update_with_fallback()
        except Exception as exception:
            raise UpdateFailed() from exception

    async def _update_with_fallback(self, retry=True):
        try:
            print(f"Hypervolt _update_with_fallback, retry = {retry}")
            return await self.api.get_state(self.api_session, self.data)
        except Exception:
            if retry:
                if self.api_session:
                    await self.api_session.close()

                self.api_session = aiohttp.ClientSession()
                await self.api.login(self.api_session)

                print(
                    "Hypervolt _update_with_fallback before notify_on_hypervolt_sync_push"
                )

                notify_on_hypervolt_sync_push_task = asyncio.create_task(
                    self.api.notify_on_hypervolt_sync_push(
                        self.api_session, self.hypervolt_sync_on_message_callback
                    )
                )

                print(
                    "Hypervolt _update_with_fallback after notify_on_hypervolt_sync_push"
                )

                return await self._update_with_fallback(False)

    def _unschedule_refresh(self):
        super()._unschedule_refresh()

        if self.api_session:
            self.api_session.close()
            self.api_session = None

    def hypervolt_sync_on_message_callback(self, message):
        try:
            # {"jsonrpc":"2.0","id":"0","result":[{"brightness":0.25},{"lock_state":"unlocked"},{"release_state":"default"},{"max_current":32000},{"ct_flags":1},{"solar_mode":"boost"},{"features":["super_eco"]},{"random_start":true}]}
            # or
            # {"method":"sync.apply","params":[{"brightness":0.25}]}
            jmsg = json.loads(message)
            res_array = None
            if "result" in jmsg:
                res_array = jmsg["result"]
            elif "params" in jmsg:
                res_array = jmsg["params"]

            if res_array:
                for item in res_array:
                    if "brightness" in item:
                        self.data.led_brightness = item["brightness"]
                    if "lock_state" in item:
                        self.data.lock_state = HypervoltLockState[
                            item["lock_state"].upper()
                        ]
                    if "max_current" in item:
                        self.data.max_current_milliamps = item["max_current"]
                    if "solar_mode" in item:
                        self.data.charge_mode = HypervoltChargeMode[
                            item["solar_mode"].upper()
                        ]
                self.async_set_updated_data(self.data)
            else:
                print(
                    f"hypervolt_sync_on_message_callback unknown message structure {message}"
                )

        except Exception as exc:
            print(f"hypervolt_sync_on_message_callback error: {exc}")
