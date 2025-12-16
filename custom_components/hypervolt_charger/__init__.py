"""The Hypervolt Charger integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, CONF_CHARGER_ID, CONF_PASSWORD, CONF_USERNAME
from .hypervolt_update_coordinator import HypervoltUpdateCoordinator
from .service import async_setup_services
from .utils import get_version_from_manifest

# Indicates this integration can only be set up via config entries
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

# There should be a file for each of the declared platforms e.g. sensor.py
PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TEXT,
    Platform.TIME,
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
    coordinator: HypervoltUpdateCoordinator | None = None

    try:
        _LOGGER.debug("Async_setup_entry enter, entry_id: %s", config.entry_id)

        # Get config values and ensure they exist
        username = config.data.get(CONF_USERNAME)
        password = config.data.get(CONF_PASSWORD)
        charger_id = config.data.get(CONF_CHARGER_ID)

        if not username or not password or not charger_id:
            raise ConfigEntryNotReady("Missing required configuration")

        coordinator = await HypervoltUpdateCoordinator.create_hypervolt_coordinator(
            hass,
            await get_version_from_manifest(),
            username,
            password,
            charger_id,
            config,
        )

        hass.data[DOMAIN][config.entry_id] = coordinator

        await coordinator.async_config_entry_first_refresh()

        if not coordinator.last_update_success:
            raise ConfigEntryNotReady("Failed to retrieve initial data")

        _LOGGER.debug("Async_setup_entry async_forward_entry_setups")
        await hass.config_entries.async_forward_entry_setups(config, PLATFORMS)
        _LOGGER.debug("Async_setup_entry async_forward_entry_setups done")

        return True
    except Exception as exc:
        _LOGGER.exception(
            "Async_setup_entry exception: %s",
            type(exc).__name__,
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

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    # Always clean up coordinator resources (websockets, sessions, etc)
    await coordinator.async_unload()

    return unload_ok
