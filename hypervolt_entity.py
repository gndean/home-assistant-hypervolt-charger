from .common_setup import HypervoltUpdateCoordinator
from .const import DOMAIN
from typing import Union, Callable, Awaitable, TypeVar
from homeassistant.helpers.entity import DeviceInfo

from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.config_entries import ConfigEntry


class HypervoltEntity(CoordinatorEntity):
    def __init__(self, coordinator: HypervoltUpdateCoordinator):
        super().__init__(coordinator)

    @property
    def _tapo_coordinator(self) -> HypervoltUpdateCoordinator:
        return self.coordinator

    @property
    def device_info(self) -> DeviceInfo:
        return {
            "identifiers": {(DOMAIN, self.coordinator.data.charger_id)},
            # "name": self.coordinator.data.nickname,
            # "model": self.coordinator.data.model,
            "manufacturer": "Hypervolt",
        }

    @property
    def unique_id(self):
        return self.coordinator.data.charger_id

    @property
    def name(self):
        return "HypervoltEntity.nickname"

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
