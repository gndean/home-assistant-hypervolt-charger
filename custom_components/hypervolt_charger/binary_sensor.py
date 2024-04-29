import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from typing import Any

from .hypervolt_update_coordinator import HypervoltUpdateCoordinator
from .hypervolt_entity import HypervoltEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    _LOGGER.debug("Binary Sensor async_setup_entry enter")

    coordinator: HypervoltUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([HypervoltCarPlugged(coordinator)])


class HypervoltCarPlugged(HypervoltEntity, BinarySensorEntity):
    @property
    def unique_id(self) -> str:
        return super().unique_id + "_car_plugged"

    @property
    def name(self) -> str:
        return super().name + " Car Plugged"

    @property
    def device_class(self) -> BinarySensorDeviceClass:
        return BinarySensorDeviceClass.PLUG

    @property
    def available(self) -> bool:
        """Return availability if setting is enabled."""
        return self.coordinator.data.car_plugged is not None

    @property
    def is_on(self) -> bool:
        """Return if the car is plugged in."""
        return self.coordinator.data.car_plugged
