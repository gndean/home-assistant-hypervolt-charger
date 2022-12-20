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

# Polling interval to get schedule/charge mode, and to re-check
# other properties that should otherwise be synced promptly via websocket pushes
# but we poll too to ensure we don't miss anything
SCAN_INTERVAL = timedelta(minutes=5)


class HypervoltUpdateCoordinator(DataUpdateCoordinator[HypervoltDeviceState]):
    @staticmethod
    async def create_hypervolt_coordinator(
        hass: HomeAssistant, username: str, password: str, charger_id: str
    ) -> "HypervoltUpdateCoordinator":
        _LOGGER.debug("Create_hypervolt_coordinator enter")
        api = HypervoltApiClient(username, password, charger_id)
        _LOGGER.debug(
            f"Create_hypervolt_coordinator HypervoltApiClient created, charger_id: {charger_id}"
        )

        coordinator = HypervoltUpdateCoordinator(hass, api=api)
        _LOGGER.debug("Create_hypervolt_coordinator HypervoltUpdateCoordinator created")
        await coordinator.async_config_entry_first_refresh()

        if not coordinator.last_update_success:
            raise Exception("Failed to retrieve initial data")

        return coordinator

    def __init__(self, hass: HomeAssistant, api: HypervoltApiClient):
        _LOGGER.debug("HypervoltUpdateCoordinator init")
        self.api = api

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)

        self.api_session = aiohttp.ClientSession()
        self.data = HypervoltDeviceState(self.api.charger_id)
        self.notify_on_hypervolt_sync_push_task = None
        self.notify_on_hypervolt_session_in_progress_push_task = None

    @property
    def hypervolt_client(self) -> HypervoltApiClient:
        return self.api

    async def _async_update_data(self):
        try:
            async with async_timeout.timeout(10):
                return await self._update_with_fallback()
        except Exception as exception:
            raise UpdateFailed() from exception

    async def _update_with_fallback(self, retry=True) -> HypervoltDeviceState:
        try:
            _LOGGER.debug(f"Hypervolt _update_with_fallback, retry = {retry}")
            state = await self.api.update_state_from_schedule(
                self.api_session, self.data
            )

            if retry:
                # No need to grab a snapshot if we've just created the sync websock
                # as a sync will immediately be done within notify_on_hypervolt_sync_push_task
                await self.api.send_sync_snapshot_request()

            _LOGGER.debug(
                "HypervoltCoordinator _update_with_fallback, retry = %s, returning state: %s",
                str(retry),
                str(state),
            )

            return state

        except Exception as exc:
            _LOGGER.debug(
                "HypervoltCoordinator _update_with_fallback, retry = %s, exception: %s",
                str(retry),
                str(exc),
            )
            if retry:
                if self.api_session:
                    await self.api_session.close()

                self.api_session = aiohttp.ClientSession()
                await self.api.login(self.api_session)

                self.notify_on_hypervolt_sync_push_task = asyncio.create_task(
                    self.api.notify_on_hypervolt_sync_push(
                        self.api_session,
                        self.get_state,
                        self.hypervolt_sync_on_message_callback,
                    )
                )

                self.notify_on_hypervolt_session_in_progress_push_task = (
                    asyncio.create_task(
                        self.api.notify_on_hypervolt_session_in_progress_push(
                            self.api_session,
                            self.get_state,
                            self.hypervolt_sync_on_message_callback,
                        )
                    )
                )

                return await self._update_with_fallback(False)
            else:
                _LOGGER.debug(
                    "HypervoltCoordinator _update_with_fallback, retry = %s, returning self.data %s",
                    str(retry),
                    str(self.data),
                )
                return self.data

    async def async_unload(self):
        if self.api_session:
            await self.api_session.close()
            self.api_session = None

        if self.notify_on_hypervolt_sync_push_task:
            was_cancelled = self.notify_on_hypervolt_sync_push_task.cancel()
            _LOGGER.debug(
                f"notify_on_hypervolt_sync_push_task was cancelled :{was_cancelled}"
            )

        if self.notify_on_hypervolt_session_in_progress_push_task:
            was_cancelled = (
                self.notify_on_hypervolt_session_in_progress_push_task.cancel()
            )
            _LOGGER.debug(
                f"notify_on_hypervolt_session_in_progress_push_task was cancelled :{was_cancelled}"
            )

    def get_state(self) -> HypervoltDeviceState:
        """Used by the HypervoltApiClient as a callback to get the current state before modifying"""
        return self.data

    def hypervolt_sync_on_message_callback(self, state: HypervoltDeviceState):
        """A callback from the HypervoltApiClient when a potential state change has been pushed to the /sync web socket"""
        self.async_set_updated_data(state)
