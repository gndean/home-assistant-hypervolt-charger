"""Binary sensor platform for Hypervolt Charger integration."""

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .hypervolt_entity import HypervoltEntity
from .hypervolt_update_coordinator import HypervoltUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up binary sensor platform."""
    _LOGGER.debug("Binary Sensor async_setup_entry enter")

    coordinator: HypervoltUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    if coordinator.api.get_charger_major_version() >= 3:
        # Plugged status is only supported on version 3
        async_add_entities([HypervoltCarPlugged(coordinator)])


class HypervoltCarPlugged(HypervoltEntity, BinarySensorEntity):
    """Binary sensor representing if a car is plugged in."""

    @property
    def unique_id(self) -> str:
        """Return unique ID for this sensor."""
        return super().unique_id + "_car_plugged"

    @property
    def name(self) -> str:
        """Return name of this sensor."""
        return super().name + " Car Plugged"

    @property
    def device_class(self) -> BinarySensorDeviceClass:
        """Return device class for this sensor."""
        return BinarySensorDeviceClass.PLUG

    @property
    def available(self) -> bool:
        """Return availability if setting is enabled."""
        return self.coordinator.data.car_plugged is not None

    @property
    def is_on(self) -> bool:
        """Return if the car is plugged in."""
        return bool(self.coordinator.data.car_plugged)
