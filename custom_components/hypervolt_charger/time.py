from __future__ import annotations
from datetime import time

from homeassistant.core import HomeAssistant
from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry

from .hypervolt_update_coordinator import HypervoltUpdateCoordinator
from .hypervolt_entity import HypervoltEntity
from .const import DOMAIN


import logging

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    _LOGGER.debug("Time async_setup_entry enter")

    coordinator: HypervoltUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    switches = [
        HypervoltScheduleTime(coordinator, True, 0),
        HypervoltScheduleTime(coordinator, False, 0),
        HypervoltScheduleTime(coordinator, True, 1),
        HypervoltScheduleTime(coordinator, False, 1),
        HypervoltScheduleTime(coordinator, True, 2),
        HypervoltScheduleTime(coordinator, False, 2),
        HypervoltScheduleTime(coordinator, True, 3),
        HypervoltScheduleTime(coordinator, False, 3),

    ]

    async_add_entities(switches)


class HypervoltScheduleTime(HypervoltEntity, TimeEntity):
    def __init__(self, coordinator: HypervoltUpdateCoordinator, is_start_time: bool, interval_index: int) -> None:
        super().__init__(coordinator)

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
        """Return the value reported by the time."""
        intervals = self._hypervolt_coordinator.data.schedule_intervals
        tm = None
        if len(intervals) > self.interval_index:
            hv_time = intervals[self.interval_index].start_time if self.is_start_time else intervals[self.interval_index].end_time
            tm = time(hv_time.hours, hv_time.minutes, hv_time.seconds)

        return tm

    def set_value(self, value: time) -> None:
        """Change the time."""
        pass
