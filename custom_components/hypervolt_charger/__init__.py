"""The Hypervolt Charger integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry, ConfigType
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry

from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD, CONF_CHARGER_ID
from .hypervolt_update_coordinator import HypervoltUpdateCoordinator
from .utils import get_version_from_manifest
from .hypervolt_device_state import (
    HypervoltActivationMode,
    HypervoltScheduleInterval,
)

# There should be a file for each of the declared platforms e.g. sensor.py
PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.TIME,
    Platform.BUTTON
]

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up hypervolt_charger component"""
    _LOGGER.debug("Async_setup enter")

    hass.data.setdefault(DOMAIN, {})

    return True


async def async_setup_entry(hass: HomeAssistant, config: ConfigEntry) -> bool:
    """Set up Hypervolt Charger from a config entry."""
    coordinator: HypervoltUpdateCoordinator = None

    try:
        _LOGGER.debug("Async_setup_entry enter, entry_id: %s", config.entry_id)

        coordinator = await HypervoltUpdateCoordinator.create_hypervolt_coordinator(
            hass,
            get_version_from_manifest(),
            config.data.get(CONF_USERNAME),
            config.data.get(CONF_PASSWORD),
            config.data.get(CONF_CHARGER_ID),
        )

        hass.data[DOMAIN][config.entry_id] = coordinator

        await coordinator.async_config_entry_first_refresh()

        if not coordinator.last_update_success:
            raise Exception("Failed to retrieve initial data")

        _LOGGER.debug("Async_setup_entry async_forward_entry_setups")
        await hass.config_entries.async_forward_entry_setups(config, PLATFORMS)
        _LOGGER.debug("Async_setup_entry async_forward_entry_setups done")

        _LOGGER.debug("Setting up schedule service")

        async def async_set_schedule(service: ha.ServiceCall) -> None:
            _LOGGER.info(f"Setting schedule intervals")

            dev_reg = device_registry.async_get(hass)
            schedule_id = service.data['schedule']

            for device_id in service.data['device_id']:
                device = dev_reg.async_get(device_id)
                if device is not None:
                    for config_id in device.config_entries:
                        coordinator: HypervoltUpdateCoordinator = hass.data[DOMAIN][config_id]
                        break
                else:
                    _LOGGER.info(f"Unknown device id: {device_id}")


            tracker = hass.states.get(schedule_id)

            if tracker is None:
                _LOGGER.info(f"Unknown entity id: {schedule}")
                return

            if tracker.attributes["last_evaluated"] is None:
                _LOGGER.info("Tracker not evaluated yet")
                return

            if tracker.attributes["rates_incomplete"] is False:
                _LOGGER.info("Tracker rates not available yet")

            target_times = tracker.attributes["target_times"]

            _LOGGER.info(f"{target_times}")

            # It would be nice to merge any continous times...
            intervals = []
            for time in tracker.attributes["target_times"]:
                    interval = HypervoltScheduleInterval(time["start"], time["end"])
                    intervals.append(interval)

           

            await coordinator.api.set_schedule(
                coordinator.api_session,
                HypervoltActivationMode.SCHEDULE,
                intervals,
                "restricted",               #coordinator.data.schedule_type,
                coordinator.data.schedule_tz
            )

            _LOGGER.info("Schedule applied. Reading back from API")

            # Read back schedule from API so that we're synced with the API
            await coordinator.force_update()

            _LOGGER.info("Read back shedule intervals")


        hass.services.async_register(DOMAIN, "set_schedule", async_set_schedule)

        return True
    except Exception as exc:
        _LOGGER.error("Async_setup_entry exception: %s", exc)
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
