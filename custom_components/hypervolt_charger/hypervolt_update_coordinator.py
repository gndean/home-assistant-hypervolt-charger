import asyncio
import logging
import async_timeout
import aiohttp

from datetime import timedelta
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
    ConfigEntryAuthFailed,
)

from .hypervolt_api_client import HypervoltApiClient, InvalidAuth
from .hypervolt_device_state import (
    HypervoltDeviceState,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Polling interval to get schedule/charge mode, and to re-check
# other properties that should otherwise be synced promptly via websocket pushes
# but we poll too to ensure we don't miss anything
SCAN_INTERVAL = timedelta(minutes=5)


class HypervoltUpdateCoordinator(DataUpdateCoordinator[HypervoltDeviceState]):
    @staticmethod
    async def create_hypervolt_coordinator(
        hass: HomeAssistant,
        version: str,
        username: str,
        password: str,
        charger_id: str,
    ) -> "HypervoltUpdateCoordinator":
        _LOGGER.debug("Create_hypervolt_coordinator enter")

        api = HypervoltApiClient(version, username, password, charger_id)
        _LOGGER.debug(
            f"Create_hypervolt_coordinator HypervoltApiClient created, charger_id: {charger_id}"
        )

        coordinator = HypervoltUpdateCoordinator(hass, api=api)
        _LOGGER.debug("Create_hypervolt_coordinator HypervoltUpdateCoordinator created")

        return coordinator

    def __init__(self, hass: HomeAssistant, api: HypervoltApiClient) -> None:
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
        except InvalidAuth as exc:
            raise ConfigEntryAuthFailed() from exc
        except asyncio.TimeoutError as exc:
            # This is handled by the UpdateCoordinator base class
            raise exc
        except Exception as exc:
            raise UpdateFailed() from exc

    async def _update_with_fallback(self, retry=True) -> HypervoltDeviceState:
        try:
            _LOGGER.debug(f"Hypervolt _update_with_fallback enter, retry = {retry}")

            # If we have an active session, try and use that now
            # If that fails, we'll re-login
            if (
                not self.api_session.closed
                and "authorization" in self.api_session.headers
            ):
                # If we're a v3 charger, we don't need to do anything, as everything is synced
                # via the sync websocket
                if self.api.get_charger_major_version() == 2:
                    _LOGGER.debug("Active session found, updating state")
                    state = await self.api.update_state_from_schedule(
                        self.api_session, self.data
                    )

            else:
                _LOGGER.debug("No active session")
                raise InvalidAuth

            if retry:
                # No need to grab a snapshot if we've just created the sync websock
                # as a sync will immediately be done within notify_on_hypervolt_sync_push_task
                await self.api.send_sync_snapshot_request()

            _LOGGER.debug(
                f"HypervoltCoordinator _update_with_fallback exit, retry = {retry}"
            )

            return state

        except Exception as exc:
            _LOGGER.debug(
                f"HypervoltCoordinator _update_with_fallback, retry = {retry}, exception: {exc}"
            )
            if retry:
                # Close websockets and session
                if self.notify_on_hypervolt_sync_push_task:
                    self.notify_on_hypervolt_sync_push_task.cancel()

                if self.notify_on_hypervolt_session_in_progress_push_task:
                    self.notify_on_hypervolt_session_in_progress_push_task.cancel()

                if self.api_session:
                    await self.api_session.close()

                self.api_session = aiohttp.ClientSession()
                access_token = await self.api.login(self.api_session)

                self.notify_on_hypervolt_sync_push_task = asyncio.create_task(
                    self.api.notify_on_hypervolt_sync_websocket(
                        self.api_session,
                        access_token,
                        self.get_state,
                        self.on_state_updated,
                    )
                )

                if self.api.get_charger_major_version() == 2:
                    # Version 2 sends messages when a session is in progress via in-progress websocket
                    # Version 3 uses the sync websocket for everything
                    self.notify_on_hypervolt_session_in_progress_push_task = (
                        asyncio.create_task(
                            self.api.notify_on_hypervolt_session_in_progress_websocket(
                                self.api_session,
                                access_token,
                                self.get_state,
                                self.on_state_updated,
                            )
                        )
                    )

                return await self._update_with_fallback(False)
            else:
                _LOGGER.debug(
                    f"HypervoltCoordinator _update_with_fallback, retry = {retry}, returning self.data"
                )

                return self.data

    async def async_unload(self):
        _LOGGER.debug("HypervoltCoordinator async_unload")

        await self.api.unload()

        if self.api_session:
            await self.api_session.close()
            self.api_session = None

        # The api.unload call above should cause the push tasks to complete
        # But we'll cancel them here too to make sure
        if self.notify_on_hypervolt_sync_push_task:
            task_name = self.notify_on_hypervolt_sync_push_task.get_name()
            was_cancelled = self.notify_on_hypervolt_sync_push_task.cancel()
            _LOGGER.debug(
                f"notify_on_hypervolt_sync_push_task {task_name} was cancelled :{was_cancelled}"
            )

        if self.notify_on_hypervolt_session_in_progress_push_task:
            task_name = (
                self.notify_on_hypervolt_session_in_progress_push_task.get_name()
            )
            was_cancelled = (
                self.notify_on_hypervolt_session_in_progress_push_task.cancel()
            )
            _LOGGER.debug(
                f"notify_on_hypervolt_session_in_progress_push_task {task_name} was cancelled :{was_cancelled}"
            )

    def get_state(self) -> HypervoltDeviceState:
        """Used by the HypervoltApiClient as a callback to get the current state before modifying"""
        return self.data

    def on_state_updated(self, state: HypervoltDeviceState):
        """A callback from the HypervoltApiClient when a potential state change has been pushed to a web socket"""
        self.async_set_updated_data(state)

    async def force_update(self):
        """Request fresh data from the HV APIs"""
        await self._async_update_data()
