import asyncio
import logging
import async_timeout
import aiohttp
import websockets

from datetime import timedelta
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.update_coordinator import UpdateFailed

from .hypervolt_api_client import HypervoltApiClient
from .hypervolt_state import HypervoltDeviceState

from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD, CONF_CHARGER_ID

_LOGGGER = logging.getLogger(__name__)


async def setup_hypervolt_coordinator_from_config_entry(
    hass: HomeAssistant, entry: ConfigEntry
) -> "HypervoltUpdateCoordinator":
    return await setup_hypervolt_coordinator(
        hass,
        entry.data.get(CONF_USERNAME),
        entry.data.get(CONF_PASSWORD),
        entry.data.get(CONF_CHARGER_ID),
    )


async def setup_hypervolt_coordinator(
    hass: HomeAssistant, username: str, password: str, charger_id: str
) -> "HypervoltUpdateCoordinator":
    session = async_get_clientsession(hass)
    api = HypervoltApiClient(username, password, charger_id)

    coordinator = HypervoltUpdateCoordinator(hass, api=api)
    await coordinator.async_config_entry_first_refresh()

    if not coordinator.last_update_success:
        raise Exception("Failed to retrieve initial data")

    return coordinator


SCAN_INTERVAL = timedelta(seconds=30)


class HypervoltUpdateCoordinator(DataUpdateCoordinator[HypervoltDeviceState]):
    def __init__(self, hass: HomeAssistant, api: HypervoltApiClient):
        self.api = api

        super().__init__(hass, _LOGGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)

        self.api_session = aiohttp.ClientSession()
        self.websocket_sync: websockets.client.WebSocketClientProtocol = None

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
            return await self.api.get_state(self.api_session)
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
                    self.notify_on_hypervolt_sync_push()
                )

                print(
                    "Hypervolt _update_with_fallback after notify_on_hypervolt_sync_push"
                )

                return await self._update_with_fallback(False)

    def _unschedule_refresh(self):
        super()._unschedule_refresh()

        # Close the sessions now
        if self.websocket_sync:
            self.websocket_sync.close()

        if self.api_session:
            self.api_session.close()
            self.api_session = None

    async def notify_on_hypervolt_sync_push(self):
        """Open websocket to /sync endpoint and notify on updates"""

        print(f"notify_on_hypervolt_sync_push enter")

        try:
            # Close any previous websocket first
            if self.websocket_sync:
                await self.websocket_sync.close()

            # Move cookies from login session to websocket
            requests_cookies = self.api_session.cookie_jar.filter_cookies(
                "https://api.hypervolt.co.uk"
            )
            cookies = ""
            for key, cookie in requests_cookies.items():
                cookies += f"{cookie.key}={cookie.value};"

            # TODO: Move this into HypervoltApiClient
            self.websocket_sync = await websockets.connect(
                f"wss://api.hypervolt.co.uk/ws/charger/{self.api.charger_id}/sync",
                extra_headers={"Cookie": cookies},
                origin="https://hypervolt.co.uk",
                host="api.hypervolt.co.uk",
            )

            # Get a snapshot now first
            await self.websocket_sync.send('{"id":"0", "method":"sync.snapshot"}')

            async for message in self.websocket_sync:
                print(f"notify_on_hypervolt_sync_push recv {message}")

        except Exception as exc:
            print(f"notify_on_hypervolt_sync_push error {exc}")

    async def hypervolt_sync_websocket_consumer_handler(self):
        async for message in self.websocket_sync:
            print(f"hypervolt_sync_websocket_consumer_handler {message}")
