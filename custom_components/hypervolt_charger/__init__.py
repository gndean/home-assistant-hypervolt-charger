"""The Hypervolt Charger integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD, CONF_CHARGER_ID
from .hypervolt_update_coordinator import HypervoltUpdateCoordinator

# There should be a file for each of the declared platforms e.g. sensor.py
PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.NUMBER,
    Platform.SELECT,
]

_LOGGER = logging.getLogger(__name__)


class HypervoltApi:
    def __init__(self, email_address, password, charger_id):
        self.email_address = email_address
        self.password = password
        self.charger_id = charger_id


async def async_setup(hass: HomeAssistant, config) -> bool:
    """Set up hypervolt_charger component"""
    _LOGGER.debug("Async_setup enter")

    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, config: ConfigEntry) -> bool:
    """Set up Hypervolt Charger from a config entry."""
    try:
        _LOGGER.debug("Async_setup_entry enter, entry_id: %s", config.entry_id)

        coordinator = await HypervoltUpdateCoordinator.create_hypervolt_coordinator(
            hass,
            config.data.get(CONF_USERNAME),
            config.data.get(CONF_PASSWORD),
            config.data.get(CONF_CHARGER_ID),
        )

        hass.data[DOMAIN][config.entry_id] = coordinator

        _LOGGER.debug(
            "Async_setup_entry async_forward_entry_setups, coordinator: %s",
            str(coordinator),
        )
        await hass.config_entries.async_forward_entry_setups(config, PLATFORMS)
        _LOGGER.debug("Async_setup_entry async_forward_entry_setups done")

        return True
    except Exception as exc:
        raise ConfigEntryNotReady from exc


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Async_unload_entry enter")

    coordinator: HypervoltUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    await coordinator.async_unload()

    return unload_ok
