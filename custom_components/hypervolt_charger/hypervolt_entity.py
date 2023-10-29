import logging

from .hypervolt_update_coordinator import HypervoltUpdateCoordinator
from .const import DOMAIN
from typing import Union, Callable, Awaitable, TypeVar
from homeassistant.helpers.entity import DeviceInfo

from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.config_entries import ConfigEntry

_LOGGER = logging.getLogger(__name__)


class HypervoltEntity(CoordinatorEntity):
    def __init__(self, coordinator: HypervoltUpdateCoordinator) -> None:
        super().__init__(coordinator)

    @property
    def _hypervolt_coordinator(self) -> HypervoltUpdateCoordinator:
        return self.coordinator

    @property
    def device_info(self) -> DeviceInfo:
        return {
            "identifiers": {(DOMAIN, self.coordinator.data.charger_id)},
            "name": f"Hypervolt {self.coordinator.data.charger_id}",
            "manufacturer": "Hypervolt",
        }

    @property
    def unique_id(self):
        return self.coordinator.data.charger_id

    @property
    def name(self):
        return "Hypervolt"

    T = TypeVar("T")

    async def _execute_with_fallback(
        self, function: Callable[[], Awaitable[T]], retry=True
    ) -> T:
        try:
            return await function()
        except Exception:
            if retry:
                await self.coordinator.api.login()
                return await self._execute_with_fallback(function, False)
