from __future__ import annotations

import logging
import time as __time

from homeassistant.config_entries import ConfigEntry, ConfigType
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry
from homeassistant.util.dt import now, get_time_zone, parse_time

from .const import DOMAIN
from .hypervolt_update_coordinator import HypervoltUpdateCoordinator
from .hypervolt_device_state import (
    HypervoltActivationMode,
    HypervoltScheduleInterval,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Service handler setup."""
    _LOGGER.debug("Setting up schedule service")

    async def async_set_schedule(service: ServiceCall) -> None:
        _LOGGER.info(f"Setting schedule intervals")

        dev_reg = device_registry.async_get(hass)
        tracker_id = service.data.get("tracker_rate", None)
        backup_start = service.data.get("backup_schedule_start", None)
        backup_end = service.data.get("backup_schedule_end", None)
        append = service.data.get("append_backup", False)
        scheduled_blocks = None
        timezone = None

        backup_available = backup_start is not None and backup_end is not None
        if backup_available:
            backup_start = parse_time(backup_start)
            backup_end = parse_time(backup_end)
            _LOGGER.debug(f"Backup times: {backup_start} -> {backup_end}")

        if append and not backup_available:
            _LOGGER.warning("Requested backup schedule appended but not provided!")

        for device_id in service.data.get("device_id", None):
            device = dev_reg.async_get(device_id)

            if device is not None:
                for config_id in device.config_entries:
                    coordinator: HypervoltUpdateCoordinator = hass.data[DOMAIN].get(
                        config_id, None
                    )
                    if coordinator is None:
                        _LOGGER.debug(f"Unknown config_id {config_id}")
                    else:
                        timezone = get_time_zone("Europe/London")  # default
                        if coordinator.data.schedule_tz:
                            timezone = get_time_zone(coordinator.data.schedule_tz)
                        break

            else:
                _LOGGER.warning(
                    f"Unknown device id, unable to set schedule: {device_id}"
                )
                return

        if tracker_id is not None:
            tracker = hass.states.get(tracker_id)

        if tracker is not None:
            if tracker.attributes.get("target_times_last_evaluated", None) is None:
                _LOGGER.info("Tracker not evaluated yet")
                if backup_available is False:
                    _LOGGER.warning(
                        "Tracker data not available and no backup set, unable to set schedule"
                    )
                    return

            if tracker.attributes.get("planned_dispatches", None) is not None:
                # Using intelligent tracker
                scheduled_blocks = tracker.attributes.get("planned_dispatches")
            else:
                if tracker.attributes.get("rates_incomplete"):
                    _LOGGER.info("Tracker rates not available yet")
                else:
                    scheduled_blocks = tracker.attributes.get("target_times", None)

        _LOGGER.debug(f"Current time: {now()}")
        _LOGGER.debug(f"Current time in HV tz: {now(timezone)}")

        intervals = []
        merged_intervals = []
        if scheduled_blocks is not None:
            _LOGGER.info(f"Scheduled blocks from tracker: {scheduled_blocks}")
            for block in scheduled_blocks:
                # Only append blocks that haven't already finished. Backup will be appended
                # regardless. Modify timezone to match the existing scheduler tz data
                if now() < block["end"].astimezone(timezone):
                    _LOGGER.debug(f"Start: {block['start']}")
                    start = block["start"].astimezone(timezone)
                    _LOGGER.debug(f"Start tz adjusted: {start}")
                    end = block["end"].astimezone(timezone)
                    interval = HypervoltScheduleInterval(start.time(), end.time())
                    intervals.append(interval)

            _LOGGER.info(f"Intervals to set:")
            for interval in intervals:
                _LOGGER.info(f"{interval.start_time} -> {interval.end_time}")

            _LOGGER.info("Merging continuous times:")
            i = 0
            while i < len(intervals):
                time_a = intervals[i]
                skip = 1
                while (i + skip) < len(intervals):
                    if time_a.end_time == intervals[i + skip].start_time:
                        time_a.end_time = intervals[i + skip].end_time
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
                merged_intervals.append(
                    HypervoltScheduleInterval(backup_start, backup_end)
                )

        else:
            if backup_available:
                _LOGGER.info(
                    f"No scheduled blocks found, using backup {backup_start} - {backup_end}"
                )
                merged_intervals.append(
                    HypervoltScheduleInterval(backup_start, backup_end)
                )

        _LOGGER.debug(f"Timezone used: {timezone}")

        await coordinator.api.set_schedule(
            coordinator.api_session,
            HypervoltActivationMode.SCHEDULE,
            merged_intervals,
            "restricted",  # coordinator.data.schedule_type,
            coordinator.data.schedule_tz,
        )

        _LOGGER.info("Schedule applied. Reading back from API")

        # Read back schedule from API so that we're synced with the API
        await coordinator.force_update()

        _LOGGER.info("Read back shedule intervals")

    # Register the service
    hass.services.async_register(DOMAIN, "set_schedule", async_set_schedule)
