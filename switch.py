from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.components.switch import SwitchEntity
from typing import Any

from .common_setup import HypervoltUpdateCoordinator

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    coordinator: HypervoltUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    switches = [ExampleSwitch()]

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
