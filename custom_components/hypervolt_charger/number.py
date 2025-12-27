"""Number entities for the Hypervolt Charger integration."""

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import PERCENTAGE
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .hypervolt_update_coordinator import HypervoltUpdateCoordinator
from .hypervolt_entity import HypervoltEntity
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: HypervoltUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            LedBrightnessNumberEntity(coordinator),
            MaxCurrentNumberEntity(coordinator),
            LedTestIndexNumberEntity(coordinator),
        ]
    )


class LedBrightnessNumberEntity(HypervoltEntity, NumberEntity):
    def __init__(self, coordinator) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)

    @property
    def unique_id(self):
        return super().unique_id + "_led_brightness"

    @property
    def name(self):
        return super().name + " LED Brightness"

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data.led_brightness is None:
            return None
        return self.coordinator.data.led_brightness * 100

    @property
    def native_min_value(self) -> float:
        return 0.0

    @property
    def native_max_value(self) -> float:
        return 100.0

    @property
    def native_step(self) -> float:
        # Match the app's step size
        return 25.0

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        await self.coordinator.api.set_led_brightness(value)

    @property
    def native_unit_of_measurement(self) -> str | None:
        return PERCENTAGE


class MaxCurrentNumberEntity(HypervoltEntity, NumberEntity):
    def __init__(self, coordinator) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)

    @property
    def unique_id(self):
        return super().unique_id + "_max_current"

    @property
    def name(self):
        return super().name + " Max Current"

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data.max_current_milliamps is None:
            return None
        return self.coordinator.data.max_current_milliamps / 1000

    @property
    def native_min_value(self) -> int:
        return 6

    @property
    def native_max_value(self) -> int:
        return 32

    async def async_set_native_value(self, value: int) -> None:
        """Update the current value."""
        await self.coordinator.api.set_max_current_milliamps(value * 1000)

    @property
    def native_unit_of_measurement(self) -> str | None:
        return "A"


class LedTestIndexNumberEntity(HypervoltEntity, NumberEntity):
    def __init__(self, coordinator) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self._value: int = 0

    @property
    def unique_id(self):
        return super().unique_id + "_led_test_index"

    @property
    def name(self):
        return super().name + " LED Test Index"

    @property
    def native_value(self) -> int:
        return self._value

    @property
    def mode(self) -> NumberMode:
        return NumberMode.SLIDER

    @property
    def native_min_value(self) -> int:
        return 0

    @property
    def native_max_value(self) -> int:
        return 50

    @property
    def native_step(self) -> int:
        return 1

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        index = int(value)
        self._value = index
        await self.coordinator.api.set_single_led_on(index)
        self.async_write_ha_state()
