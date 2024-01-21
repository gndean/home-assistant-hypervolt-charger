from dataclasses import dataclass
import logging
from typing import Optional

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfMass,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .hypervolt_device_state import HypervoltReleaseState
from .hypervolt_entity import HypervoltEntity
from .hypervolt_update_coordinator import HypervoltUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: HypervoltUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    sensors = [
        HypervoltSensor(
            coordinator,
            "Session ID",
            "session_id",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        HypervoltSensor(
            coordinator,
            "Session Energy",
            "session_watthours",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL,
            unit_of_measure=UnitOfEnergy.WATT_HOUR,
        ),
        HypervoltSensor(
            coordinator,
            "Session Energy Total Increasing",
            "session_watthours_total_increasing",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
            unit_of_measure=UnitOfEnergy.WATT_HOUR,
        ),
        HypervoltSensor(
            coordinator,
            "Session Carbon Saved",
            "session_carbon_saved_grams",
            device_class=SensorDeviceClass.WEIGHT,
            state_class=SensorStateClass.MEASUREMENT,
            unit_of_measure=UnitOfMass.GRAMS,
        ),
        HypervoltSensor(
            coordinator,
            "Charger Current",
            "current_session_current_milliamps",
            device_class=SensorDeviceClass.CURRENT,
            state_class=SensorStateClass.MEASUREMENT,
            unit_of_measure=UnitOfElectricCurrent.AMPERE,
            scale_factor=0.001,
        ),
        HypervoltSensor(
            coordinator,
            "CT Current",
            "current_session_ct_current",
            device_class=SensorDeviceClass.CURRENT,
            state_class=SensorStateClass.MEASUREMENT,
            unit_of_measure=UnitOfElectricCurrent.AMPERE,
            scale_factor=0.001,
        ),
        HypervoltSensor(
            coordinator,
            "CT Power",
            "current_session_ct_power",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            unit_of_measure=UnitOfPower.WATT,
        ),
        HypervoltSensor(
            coordinator,
            "Voltage",
            "current_session_voltage",
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            unit_of_measure=UnitOfElectricPotential.VOLT,
        ),
        HypervoltSensor(
            coordinator,
            "Session Power",
            "current_session_power",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            unit_of_measure=UnitOfPower.WATT,
        ),
        ChargingReadinessSensor(coordinator),
    ]

    async_add_entities(sensors)


class HypervoltSensor(HypervoltEntity, SensorEntity):
    def __init__(
        self,
        coordinator: HypervoltUpdateCoordinator,
        name: str,
        state_property_name: str,
        device_class: SensorDeviceClass = None,
        state_class: str = SensorStateClass.MEASUREMENT,
        unit_of_measure: str = None,
        scale_factor: float = None,
    ):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)

        # Use sub-obj
        self.hv_name = name
        self.hv_state_property_name = state_property_name
        self.hv_device_class = device_class
        self.hv_state_class = state_class
        self.hv_unit_of_measure = unit_of_measure
        self.hv_scale_factor = scale_factor

    @property
    def unique_id(self):
        return super().unique_id + "_" + self.hv_name.replace(" ", "_")

    @property
    def name(self):
        return super().name + " " + self.hv_name

    @property
    def native_value(self):
        val = getattr(self._hypervolt_coordinator.data, self.hv_state_property_name)
        if self.hv_scale_factor and val:
            return val * self.hv_scale_factor
        else:
            return val

    @property
    def device_class(self) -> Optional[str]:
        return self.hv_device_class

    @property
    def state_class(self) -> Optional[str]:
        return self.hv_state_class

    @property
    def native_unit_of_measurement(self) -> Optional[str]:
        return self.hv_unit_of_measure


class ChargingReadinessSensor(HypervoltEntity, SensorEntity):
    def __init__(self, coordinator: HypervoltUpdateCoordinator):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)

    @property
    def unique_id(self):
        return super().unique_id + "_charging_readiness"

    @property
    def name(self):
        return super().name + " Charging Readiness"

    @property
    def native_value(self):
        if (
            self._hypervolt_coordinator.data.is_charging is None
            or self._hypervolt_coordinator.data.release_state is None
        ):
            return None

        if self._hypervolt_coordinator.data.is_charging:
            return "Charging"
        elif (
            self._hypervolt_coordinator.data.release_state
            == HypervoltReleaseState.RELEASED
        ):
            return "Not Ready - Force Stopped"
        else:
            return "Ready"
