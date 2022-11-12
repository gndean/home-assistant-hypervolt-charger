import logging
import async_timeout

from datetime import timedelta
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.update_coordinator import UpdateFailed

from .hypervolt_api_client import HypervoltApiClientConfig, HypervoltApiClient
from .hypervolt_state import HypervoltDeviceState

from .const import (
    DOMAIN,
    CONF_USERNAME,
    CONF_PASSWORD,
)

_LOGGGER = logging.getLogger(__name__)


async def setup_hypervolt_coordinator_from_config_entry(
    hass: HomeAssistant, entry: ConfigEntry
) -> "HypervoltUpdateCoordinator":
    return await setup_hypervolt_coordinator(
        hass,
        entry.data.get(CONF_USERNAME),
        entry.data.get(CONF_PASSWORD),
    )


async def setup_hypervolt_coordinator(
    hass: HomeAssistant, username: str, password: str
) -> "HypervoltUpdateCoordinator":
    session = async_get_clientsession(hass)
    config = HypervoltApiClientConfig(username, password, session)
    client = HypervoltApiClient.from_config(config)

    coordinator = HypervoltUpdateCoordinator(hass, client=client)
    await coordinator.async_config_entry_first_refresh()

    if not coordinator.last_update_success:
        raise Exception("Failed to retrieve initial data")

    return coordinator


SCAN_INTERVAL = timedelta(seconds=30)


class HypervoltUpdateCoordinator(DataUpdateCoordinator[HypervoltDeviceState]):
    def __init__(self, hass: HomeAssistant, client: HypervoltApiClient):
        self.api = client

        super().__init__(hass, _LOGGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)

    @property
    def tapo_client(self) -> HypervoltApiClient:
        return self.api

    async def _async_update_data(self):
        try:
            async with async_timeout.timeout(10):
                return await self._update_with_fallback()
        except Exception as exception:
            raise UpdateFailed() from exception

    async def _update_with_fallback(self, retry=True):
        try:
            # TODO
            return await self.api.get_state()
        except Exception as error:
            if retry:
                # TODO
                await self.api.login()
                return await self._update_with_fallback(False)
