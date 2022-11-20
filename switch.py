from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.components.switch import SwitchEntity
from typing import Any

from .hypervolt_update_coordinator import HypervoltUpdateCoordinator
from .hypervolt_entity import HypervoltEntity
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    coordinator: HypervoltUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    switches = [HypervoltChargingSwitch(coordinator)]

    async_add_entities(switches)


class ExampleSwitch(SwitchEntity):
    @property
    def is_on(self):
        """Return true if switch is on."""
        return False

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        pass

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        pass

    def update(self) -> None:
        """Update the switch's state."""
        pass


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
