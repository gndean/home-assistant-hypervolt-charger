from __future__ import annotations
from datetime import time
from copy import deepcopy

from homeassistant.core import HomeAssistant
from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry

from .hypervolt_update_coordinator import HypervoltUpdateCoordinator
from .hypervolt_entity import HypervoltEntity
from .hypervolt_device_state import HypervoltScheduleInterval
from .const import DOMAIN

import logging

_LOGGER = logging.getLogger(__name__)

NUM_SCHEDULE_INTERVALS = 4


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    _LOGGER.debug("Time async_setup_entry enter")

    coordinator: HypervoltUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Create a switch for each schedule interval
    switches = []
    for interval_index in range(NUM_SCHEDULE_INTERVALS):
        switches.append(HypervoltScheduleTime(coordinator, True, interval_index))
        switches.append(HypervoltScheduleTime(coordinator, False, interval_index))
    async_add_entities(switches)


class HypervoltScheduleTime(HypervoltEntity, TimeEntity):
    def __init__(
        self,
        coordinator: HypervoltUpdateCoordinator,
        is_start_time: bool,
        interval_index: int,
    ) -> None:
        super(HypervoltScheduleTime, self).__init__(coordinator)

        self._attr_native_value = None
        self.is_start_time = is_start_time
        self.interval_index = interval_index

    @property
    def unique_id(self):
        name_prefix = "start" if self.is_start_time else "end"
        return f"{super().unique_id}_schedule_session_{self.interval_index+1}_{name_prefix}_time"

    @property
    def name(self):
        name_suffix = "Start" if self.is_start_time else "End"
        return f"{super().name} Schedule Session {self.interval_index+1} {name_suffix} Time"

    @property
    def native_value(self) -> time | None:
        """Return the start or end time defined in the schedule, or None if the session doesn't exist."""
        intervals = self._hypervolt_coordinator.data.schedule_intervals_to_apply
        tm = None
        if (
            intervals
            and len(intervals) > self.interval_index
            and intervals[self.interval_index]
        ):
            tm = (
                intervals[self.interval_index].start_time
                if self.is_start_time
                else intervals[self.interval_index].end_time
            )

        return tm

    async def async_set_value(self, value: time) -> None:
        """Set the start or end time defined in the schedule."""

        # First create an array of the max size, and fill it with the existing values
        new_intervals: list[HypervoltScheduleInterval] = [None] * NUM_SCHEDULE_INTERVALS
        intervals = self._hypervolt_coordinator.data.schedule_intervals_to_apply
        if intervals:
            for i, interval in enumerate(intervals):
                new_intervals[i] = deepcopy(interval)
        else:
            new_intervals = [None] * NUM_SCHEDULE_INTERVALS

        # Now set the new value
        if not new_intervals[self.interval_index]:
            new_intervals[self.interval_index] = HypervoltScheduleInterval(
                time(), time()
            )

        if self.is_start_time:
            new_intervals[self.interval_index].start_time = value
        else:
            new_intervals[self.interval_index].end_time = value

        self._hypervolt_coordinator.data.schedule_intervals_to_apply = new_intervals
