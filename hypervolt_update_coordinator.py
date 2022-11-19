import asyncio
import logging
import async_timeout
import aiohttp
import json
import websockets

from datetime import timedelta
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

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)


class HypervoltUpdateCoordinator(DataUpdateCoordinator[HypervoltDeviceState]):
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

    def __init__(self, hass: HomeAssistant, api: HypervoltApiClient):
        self.api = api

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)

        self.api_session = aiohttp.ClientSession()
        self.websocket_sync: websockets.client.WebSocketClientProtocol = None
        self.data = HypervoltDeviceState(self.api.charger_id)

    @property
    def hypervolt_client(self) -> HypervoltApiClient:
        return self.api

    async def _async_update_data(self):
        try:
            async with async_timeout.timeout(10):
                return await self._update_with_fallback()
        except Exception as exception:
            raise UpdateFailed() from exception

    async def _update_with_fallback(self, retry=True):
        try:
            print(f"Hypervolt _update_with_fallback, retry = {retry}")
            return await self.api.update_state_with_schedule(
                self.api_session, self.data
            )
        except Exception:
            if retry:
                if self.api_session:
                    await self.api_session.close()

                self.api_session = aiohttp.ClientSession()
                await self.api.login(self.api_session)

                notify_on_hypervolt_sync_push_task = asyncio.create_task(
                    self.api.notify_on_hypervolt_sync_push(
                        self.api_session,
                        self.get_state,
                        self.hypervolt_sync_on_message_callback,
                    )
                )

                return await self._update_with_fallback(False)

    def _unschedule_refresh(self):
        super()._unschedule_refresh()

        if self.api_session:
            self.api_session.close()
            self.api_session = None

    def get_state(self) -> HypervoltDeviceState:
        """Used by the HypervoltApiClient as a callback to get the current state before modifying"""
        return self.data

    def hypervolt_sync_on_message_callback(self, state: HypervoltDeviceState):
        """A callback from the HypervoltApiClient when a potential state change has been pushed to the /sync web socket"""
        self.async_set_updated_data(state)
