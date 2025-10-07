import asyncio
import logging
import async_timeout
import aiohttp

from datetime import timedelta, datetime, UTC
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
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


class HypervoltUpdateCoordinator(DataUpdateCoordinator[HypervoltDeviceState]):
    @staticmethod
    async def create_hypervolt_coordinator(
        hass: HomeAssistant,
        version: str,
        username: str,
        password: str,
        charger_id: str,
        config_entry: ConfigEntry,
    ) -> "HypervoltUpdateCoordinator":
        _LOGGER.debug("Create_hypervolt_coordinator enter")

        api = HypervoltApiClient(version, username, password, charger_id)
        _LOGGER.debug(
            f"Create_hypervolt_coordinator HypervoltApiClient created, charger_id: {charger_id}"
        )

        coordinator = HypervoltUpdateCoordinator(
            hass, api=api, config_entry=config_entry
        )
        _LOGGER.debug("Create_hypervolt_coordinator HypervoltUpdateCoordinator created")

        return coordinator

    def __init__(
        self, hass: HomeAssistant, api: HypervoltApiClient, config_entry: ConfigEntry
    ) -> None:
        _LOGGER.debug("HypervoltUpdateCoordinator init")
        self.api = api
        self.config_entry = config_entry

        # Polling interval to get schedule/charge mode, and to re-check
        # other properties that should otherwise be synced promptly via websocket pushes
        # but we poll too to ensure we don't miss anything
        # Note that websocket updates that result in async_on_state_updated() being called
        # reset this interval timer so for V3 devices with regular pushes, we may never poll.
        self.poll_interval = timedelta(minutes=5)

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=self.poll_interval)

        self.api_session = None
        self.data = HypervoltDeviceState(self.api.charger_id)
        self.notify_on_hypervolt_sync_push_task = None
        self.notify_on_hypervolt_session_in_progress_push_task = None
        self.reload_task = None  # Track reload task to prevent garbage collection

        # Staleness detection thresholds
        # For V3 devices, if we haven't received a websocket message in this time, force reconnection
        # In practice, we only check during the poll_interval so set this slightly less than that
        self.websocket_staleness_threshold = timedelta(minutes=4)

        # After detecting staleness, wait this long before attempting another reconnection
        # This prevents hammering the servers if the backend has stopped sending data
        self.websocket_stale_reconnect_backoff = timedelta(minutes=50)

        # Track when we last attempted a reconnection due to staleness
        # Retrieve from hass.data to persist across reloads
        self._stale_reload_key = f"{DOMAIN}_{config_entry.entry_id}_last_stale_reload"
        self.last_stale_reconnect_attempt: datetime | None = hass.data.get(
            self._stale_reload_key
        )

    @property
    def hypervolt_client(self) -> HypervoltApiClient:
        return self.api

    async def _async_update_data(self):
        _LOGGER.debug("HypervoltCoordinator _async_update_data enter")

        try:
            async with async_timeout.timeout(30):
                return await self._update()
        except InvalidAuth as exc:
            raise ConfigEntryAuthFailed() from exc
        except asyncio.TimeoutError as exc:
            # This is handled by the UpdateCoordinator base class
            raise exc
        except Exception as exc:
            raise UpdateFailed() from exc

        finally:
            _LOGGER.debug("HypervoltCoordinator _async_update_data exit")

    async def _update(self) -> HypervoltDeviceState:
        """Return updated data from the Hypervolt API.

        Refresh the access token if it's soon to expire.
        For a V2 charger, we need to poll the schedule to get the current state
        For a V3 charger, so long as we have a valid session, we can just return the current state as all state
        is updated via the sync websocket.
        If we're not logged in, we re-login and re-establish websockets (or do this for the first time)
        Note: This method will not be called periodically when on_state_updated() is regularly called (as is the
        case with a v3 charger), as calls to on_state_updated() reset the update interval.
        """
        try:
            _LOGGER.debug("Hypervolt _update enter")

            # If we have an active session, check if it's actually alive
            if (
                self.api_session
                and not self.api_session.closed
                and "authorization" in self.api_session.headers
                and self.api.websocket_sync
            ):
                # Check for websocket staleness (no messages received recently)
                # Only for V3+ chargers - V2 chargers don't send regular data
                if (
                    self.api.get_charger_major_version() >= 3
                    and self._is_websocket_stale()
                ):
                    # Check if we're in the backoff period after a recent stale reconnection attempt
                    if self._should_skip_stale_reconnect():
                        _LOGGER.debug(
                            "WebSocket appears stale, but skipping reconnection due to backoff period"
                        )
                    else:
                        _LOGGER.warning(
                            "WebSocket connection appears stale (no messages for %s). "
                            "Reloading entire integration",
                            self.websocket_staleness_threshold,
                        )
                        # Track this reconnection attempt in both instance and hass.data
                        # (hass.data persists across reloads)
                        self.last_stale_reconnect_attempt = datetime.now(UTC)
                        self.hass.data[self._stale_reload_key] = (
                            self.last_stale_reconnect_attempt
                        )

                        # Go nuclear: reload the entire integration
                        self.reload_task = asyncio.create_task(
                            self.hass.config_entries.async_schedule_reload(
                                self.config_entry.entry_id
                            )
                        )

                        # Return current data while reload is happening
                        return self.data

                await self.check_for_access_token_expiry()

                _LOGGER.debug("HypervoltCoordinator _update exit")

                return self.data

            raise InvalidAuth("No active session")

        except Exception as exc:
            _LOGGER.debug(
                f"HypervoltCoordinator _update, exception: {type(exc).__name__}: {str(exc)}"
            )

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
                    self.async_on_state_updated,
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
                            self.async_on_state_updated,
                        )
                    )
                )

                try:
                    state = await self.api.v2_update_state_from_schedule(
                        self.api_session, self.data
                    )
                    _LOGGER.debug(
                        f"HypervoltCoordinator _update returning state from v2_update_state_from_schedule"
                    )
                    return state

                except Exception as exc2:
                    # Report exception but return current state to prevent
                    # the coordinator from being marked as failed
                    _LOGGER.error(
                        f"HypervoltCoordinator _update v2_update_state_from_schedule, exception: {type(exc2).__name__}: {str(exc2)}"
                    )
                    # Return the current state
                    return self.data

            else:
                _LOGGER.debug(f"HypervoltCoordinator _update returning current state")
                return self.data

    def _is_websocket_stale(self) -> bool:
        """Check if the websocket connection is stale (connected but not receiving data).

        Returns True if:
        - We haven't had any websocket activity within the staleness threshold

        Returns False if:
        - We don't have a timestamp yet (websocket not connected)
        - Activity (connection or messages) is recent
        """
        if self.api.last_websocket_activity_time is None:
            # WebSocket not connected yet
            _LOGGER.debug("WebSocket not connected yet - not considering stale")
            return False

        # Calculate time since last activity (either connection or message)
        time_since_last_activity = (
            datetime.now(UTC) - self.api.last_websocket_activity_time
        )

        is_stale = time_since_last_activity > self.websocket_staleness_threshold

        if is_stale:
            _LOGGER.debug(
                "WebSocket staleness check: last activity was %s ago (threshold: %s)",
                time_since_last_activity,
                self.websocket_staleness_threshold,
            )

        return is_stale

    def _should_skip_stale_reconnect(self) -> bool:
        """Check if we should skip reconnection attempt due to backoff period.

        Returns True if:
        - We've attempted a stale reconnection recently (within backoff period)

        Returns False if:
        - We've never attempted a stale reconnection
        - Enough time has passed since the last attempt
        """
        if self.last_stale_reconnect_attempt is None:
            return False

        time_since_last_attempt = datetime.now(UTC) - self.last_stale_reconnect_attempt

        should_skip = time_since_last_attempt < self.websocket_stale_reconnect_backoff

        if should_skip:
            _LOGGER.debug(
                "Skipping stale reconnection attempt: last attempt was %s ago (backoff: %s)",
                time_since_last_attempt,
                self.websocket_stale_reconnect_backoff,
            )

        return should_skip

    async def check_for_access_token_expiry(self):
        """Check if our access token is about to expire
        and if so, proactively refresh it.
        """

        seconds_to_expiry = (
            self.api.get_access_token_expiry() - datetime.now(UTC)
        ).total_seconds()
        if seconds_to_expiry < self.poll_interval.total_seconds() * 1.5:
            _LOGGER.debug(
                f"Access token is about to expire in {seconds_to_expiry:.0f} seconds, attempting to refresh it"
            )
            # login() will perform a token refresh in preference to a full login
            access_token = await self.api.login(self.api_session)

            # Close websockets and session
            _LOGGER.debug("Closing and recreating websockets with new access token")
            if self.notify_on_hypervolt_sync_push_task:
                self.notify_on_hypervolt_sync_push_task.cancel()

            if self.notify_on_hypervolt_session_in_progress_push_task:
                self.notify_on_hypervolt_session_in_progress_push_task.cancel()

            self.notify_on_hypervolt_sync_push_task = asyncio.create_task(
                self.api.notify_on_hypervolt_sync_websocket(
                    self.api_session,
                    access_token,
                    self.get_state,
                    self.async_on_state_updated,
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
                            self.async_on_state_updated,
                        )
                    )
                )

        # If we're a v3 charger, we don't need to do anything, as everything is synced
        # via the sync websocket
        # If we're a v2 charger, we need to request the schedule via a specific endpoint
        if self.api.get_charger_major_version() == 2:
            _LOGGER.debug("Active session found, updating state")
            self.data = await self.api.v2_update_state_from_schedule(
                self.api_session, self.data
            )

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

    async def async_on_state_updated(self, state: HypervoltDeviceState):
        """A callback from the HypervoltApiClient when a potential state change has been pushed to a web socket"""
        # Reset the stale reconnect backoff timer since we received data
        # This allows us to quickly detect staleness again if data stops flowing
        self.last_stale_reconnect_attempt = None

        self.async_set_updated_data(state)

        # Now check if we need to update our refresh token
        await self.check_for_access_token_expiry()

    async def force_update(self):
        """Request fresh data from the HV APIs"""
        await self._async_update_data()
