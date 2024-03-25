"""The Hypervolt Charger integration."""
from __future__ import annotations

import logging
import time as __time
from datetime import datetime

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
            tracker_id = service.data.get('tracker_rate', None)
            backup_start = service.data.get('backup_schedule_start', None)
            backup_end = service.data.get('backup_schedule_end', None)
            append = service.data.get('append_backup', False)
            scheduled_blocks = None

            backup_available = (backup_start is not None and backup_end is not None)
            if backup_available:
                backup_start = datetime(*(__time.strptime(backup_start,"%H:%M:%S")[0:6]))
                backup_end = datetime(*(__time.strptime(backup_end,"%H:%M:%S")[0:6]))

            if append and not backup_available:
                _LOGGER.warning("Requested backup schedule appended but not provided!")

            for device_id in service.data.get('device_id', None):
                device = dev_reg.async_get(device_id)

                if device is not None:
                    for config_id in device.config_entries:
                        coordinator: HypervoltUpdateCoordinator = hass.data[DOMAIN][config_id]
                        break
                else:
                    _LOGGER.warning(f"Unknown device id, unable to set schedule: {device_id}")
                    return

            if tracker_id is not None:
                tracker = hass.states.get(tracker_id)

            if tracker is not None:
                if tracker.attributes.get("last_evaluated", None) is None:
                    _LOGGER.info("Tracker not evaluated yet")
                    if backup_available is False:
                        _LOGGER.warning("Tracker data not available and no backup set, unable to set schedule")
                        return

                if tracker.attributes.get("planned_dispatches", None) is not None:
                    # Using intelligent tracker
                    scheduled_blocks = tracker.attributes.get("planned_dispatches")
                else:
                    if tracker.attributes.get("rates_incomplete"):
                        _LOGGER.info("Tracker rates not available yet")
                    else:
                        scheduled_blocks = tracker.attributes.get("target_times", None)

            intervals = []
            merged_intervals = []
            if scheduled_blocks is not None:

                _LOGGER.info(f"Scheduled blocks from tracker: {scheduled_blocks}")
                for block in scheduled_blocks:
                    # Only append blocks that haven't already finished. Backup will be appended
                    # regardless
                    if datetime.now().astimezone() < block["end"]:
                        interval = HypervoltScheduleInterval(block["start"], block["end"])
                        intervals.append(interval)

                _LOGGER.info(f"Intervals to set:")
                for interval in intervals:
                    _LOGGER.info(f"{interval.start_time} -> {interval.end_time}")

                _LOGGER.info("Merging continous times:")
                i = 0
                while i < len(intervals):
                    time_a = intervals[i]
                    skip = 1
                    while (i+skip) < len(intervals):
                        if time_a.end_time == intervals[i+skip].start_time:
                            time_a.end_time = intervals[i+skip].end_time
                            skip = skip + 1
                        else:
                            break
                    i = i + skip
                    merged_intervals.append(time_a)

                for interval in merged_intervals:
                    _LOGGER.info(f"{interval.start_time} -> {interval.end_time}")

                # Hypervolt will apply a schedule even if it overlaps existing schedules but
                # have not tested how this is interpreted by the charger in reality
                if append and backup_available:
                    _LOGGER.info(f"Appending backup {backup_start} -> {backup_end}")
                    merged_intervals.append(HypervoltScheduleInterval(backup_start, backup_end))

            else:
                if backup_available:
                    _LOGGER.info(f"No scheduled blocks found, using backup {backup_start} - {backup_end}")
                    intervals.append(HypervoltScheduleInterval(backup_start, backup_end))

            await coordinator.api.set_schedule(
                coordinator.api_session,
                HypervoltActivationMode.SCHEDULE,
                merged_intervals,
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
