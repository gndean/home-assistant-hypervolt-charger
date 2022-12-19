import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.components.switch import SwitchEntity
from typing import Any

from .hypervolt_update_coordinator import HypervoltUpdateCoordinator
from .hypervolt_entity import HypervoltEntity
from .hypervolt_device_state import HypervoltLockState
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    _LOGGER.debug("Switch async_setup_entry enter")

    coordinator: HypervoltUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    _LOGGER.debug("Switch coordinator data: %s", coordinator.data)

    switches = [
        HypervoltChargingSwitch(coordinator),
        HypervoltLockStateSwitch(coordinator),
    ]

    async_add_entities(switches)


class HypervoltChargingSwitch(HypervoltEntity, SwitchEntity):
    @property
    def is_on(self):
        device_state = self._hypervolt_coordinator.data
        return device_state.is_charging

    async def async_turn_on(self):
        await self._hypervolt_coordinator.api.set_charging(True)

    async def async_turn_off(self):
        await self._hypervolt_coordinator.api.set_charging(False)

    @property
    def unique_id(self):
        return super().unique_id + "_charging"

    @property
    def name(self):
        return super().name + " Charging"


class HypervoltLockStateSwitch(HypervoltEntity, SwitchEntity):
    @property
    def is_on(self):
        device_state = self._hypervolt_coordinator.data
        return (
            device_state.lock_state == HypervoltLockState.LOCKED
            or device_state.lock_state == HypervoltLockState.PENDING_LOCK
        )

    async def async_turn_on(self):
        await self._hypervolt_coordinator.api.set_lock_state(
            self._hypervolt_coordinator.api_session, True
        )

    async def async_turn_off(self):
        await self._hypervolt_coordinator.api.set_lock_state(
            self._hypervolt_coordinator.api_session, False
        )

    @property
    def unique_id(self):
        return super().unique_id + "_lock_state"

    @property
    def name(self):
        return super().name + " Lock State"
