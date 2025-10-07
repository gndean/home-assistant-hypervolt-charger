"""The Hypervolt Charger integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry, ConfigType
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD, CONF_CHARGER_ID
from .hypervolt_update_coordinator import HypervoltUpdateCoordinator
from .utils import get_version_from_manifest
from .service import async_setup_services

# There should be a file for each of the declared platforms e.g. sensor.py
PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.TIME,
    Platform.BUTTON,
    Platform.TEXT,
    Platform.BINARY_SENSOR,
]

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up hypervolt_charger component"""
    _LOGGER.debug("Async_setup enter")

    hass.data.setdefault(DOMAIN, {})

    # Services
    await async_setup_services(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, config: ConfigEntry) -> bool:
    """Set up Hypervolt Charger from a config entry."""
    coordinator: HypervoltUpdateCoordinator = None

    try:
        _LOGGER.debug("Async_setup_entry enter, entry_id: %s", config.entry_id)

        coordinator = await HypervoltUpdateCoordinator.create_hypervolt_coordinator(
            hass,
            await get_version_from_manifest(),
            config.data.get(CONF_USERNAME),
            config.data.get(CONF_PASSWORD),
            config.data.get(CONF_CHARGER_ID),
            config,
        )

        hass.data[DOMAIN][config.entry_id] = coordinator

        await coordinator.async_config_entry_first_refresh()

        if not coordinator.last_update_success:
            raise Exception("Failed to retrieve initial data")

        _LOGGER.debug("Async_setup_entry async_forward_entry_setups")
        await hass.config_entries.async_forward_entry_setups(config, PLATFORMS)
        _LOGGER.debug("Async_setup_entry async_forward_entry_setups done")

        return True
    except Exception as exc:
        _LOGGER.error(
            f"Async_setup_entry exception:  {type(exc).__name__}: {str(exc)}", exc
        )
        # Because we re-raise here, HA will retry async_setup_entry so we need
        # to make sure we clean up any existing coordinator
        if coordinator:
            await coordinator.async_unload()

        raise ConfigEntryNotReady from exc


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Async_unload_entry enter")

    coordinator: HypervoltUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    await coordinator.async_unload()

    return unload_ok
