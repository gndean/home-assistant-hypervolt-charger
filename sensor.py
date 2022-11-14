from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from dataclasses import dataclass
from typing import Optional
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.const import UnitOfEnergy, PERCENTAGE

from .hypervolt_update_coordinator import HypervoltUpdateCoordinator
from .hypervolt_entity import HypervoltEntity
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: HypervoltUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    await coordinator.async_config_entry_first_refresh()

    sensors = [
        HypervoltSensor(
            coordinator,
            SensorConfig("Last session ID", None, SensorStateClass.MEASUREMENT, None),
        ),
        HypervoltSensor(
            coordinator,
            SensorConfig(
                "Last session energy",
                SensorDeviceClass.ENERGY,
                SensorStateClass.TOTAL,
                UnitOfEnergy.KILO_WATT_HOUR,
            ),
        ),
        HypervoltLedBrightnessSensor(coordinator),
    ]

    async_add_entities(sensors)


@dataclass
class SensorConfig:
    name: str
    device_class: str
    state_class: str
    unit_measure: str


class HypervoltSensor(HypervoltEntity, SensorEntity):
    def __init__(self, coordinator, sensor_config: SensorConfig):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self.sensor_config = sensor_config

    @property
    def unique_id(self):
        return super().unique_id + "_" + self.sensor_config.name.replace(" ", "_")

    @property
    def name(self):
        return super().name + " " + self.sensor_config.name

    @property
    def device_class(self) -> Optional[str]:
        return self.sensor_config.device_class

    @property
    def state_class(self) -> Optional[str]:
        return self.sensor_config.state_class

    @property
    def native_unit_of_measurement(self) -> Optional[str]:
        return self.sensor_config.unit_measure


class HypervoltLedBrightnessSensor(HypervoltSensor):
    def __init__(self, coordinator):
        super().__init__(
            coordinator,
            SensorConfig(
                "LED Brightness",
                None,
                SensorStateClass.MEASUREMENT,
                PERCENTAGE,
            ),
        )

    @property
    def native_value(self):
        if self._hypervolt_coordinator.data.led_brightness == None:
            return None
        else:
            return self._hypervolt_coordinator.data.led_brightness * 100
