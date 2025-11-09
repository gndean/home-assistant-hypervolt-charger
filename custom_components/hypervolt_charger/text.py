from __future__ import annotations
from datetime import time
from copy import deepcopy

from homeassistant.core import HomeAssistant
from homeassistant.components.text import TextEntity
from homeassistant.config_entries import ConfigEntry

from .hypervolt_update_coordinator import HypervoltUpdateCoordinator
from .hypervolt_entity import HypervoltEntity
from .hypervolt_device_state import (
    HypervoltScheduleInterval,
    NUM_SCHEDULE_INTERVALS,
    HypervoltDayOfWeek,
)
from .const import DOMAIN
from .utils import get_days_from_days_of_week

import logging

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    _LOGGER.debug("Text async_setup_entry enter")

    coordinator: HypervoltUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []

    # Charger name entity for all versions
    entities.append(HypervoltChargerName(coordinator))

    if coordinator.api.get_charger_major_version() >= 3:
        # Create a text entity for each schedule interval
        for interval_index in range(NUM_SCHEDULE_INTERVALS):
            entities.append(HypervoltScheduleDaysOfWeek(coordinator, interval_index))

    async_add_entities(entities)


class HypervoltChargerName(HypervoltEntity, TextEntity):
    """Text entity for the charger name."""

    def __init__(self, coordinator: HypervoltUpdateCoordinator) -> None:
        super(HypervoltChargerName, self).__init__(coordinator)
        self._attr_native_min = 1
        self._attr_native_max = 250  # Reasonable max length for a name
        self._attr_pattern = None  # Allow any characters

    @property
    def unique_id(self):
        return f"{super().unique_id}_charger_name"

    @property
    def name(self):
        return f"{super().name} Charger Name"

    @property
    def native_value(self) -> str | None:
        """Return the current charger name."""
        return self.coordinator.data.charger_name

    async def async_set_value(self, value: str) -> None:
        """Set the charger name."""
        await self.coordinator.api.set_charger_name(value)

        # Optimistically update the state
        self.coordinator.data.charger_name = value
        self.async_write_ha_state()


class HypervoltScheduleDaysOfWeek(HypervoltEntity, TextEntity):
    def __init__(
        self,
        coordinator: HypervoltUpdateCoordinator,
        interval_index: int,
    ) -> None:
        super(HypervoltScheduleDaysOfWeek, self).__init__(coordinator)

        self._attr_native_value = None
        self.interval_index = interval_index

    @property
    def unique_id(self):
        return f"{super().unique_id}_schedule_session_{self.interval_index + 1}_days_of_week"

    @property
    def name(self):
        return f"{super().name} Schedule Session {self.interval_index + 1} Days Of Week"

    @property
    def native_value(self) -> time | None:
        """Return the start or end time defined in the schedule, or None if the session doesn't exist."""
        intervals = self.coordinator.data.schedule_intervals_to_apply
        if (
            intervals
            and len(intervals) > self.interval_index
            and intervals[self.interval_index]
        ):
            days = get_days_from_days_of_week(
                intervals[self.interval_index].days_of_week
            )
            return ",".join(days)

        return ""

    async def async_set_value(self, value: time) -> None:
        """Set the start or end time defined in the schedule."""

        # Convert string to days int
        days = 0
        for day in HypervoltDayOfWeek:
            if day.name in value:
                days |= day.value

        if days:
            # First create an array of the max size, and fill it with the existing values
            new_intervals: list[HypervoltScheduleInterval] = [
                None
            ] * NUM_SCHEDULE_INTERVALS
            intervals = self.coordinator.data.schedule_intervals_to_apply
            if intervals:
                for i, interval in enumerate(intervals):
                    new_intervals[i] = deepcopy(interval)

            if not new_intervals[self.interval_index]:
                new_intervals[self.interval_index] = HypervoltScheduleInterval(
                    None, None
                )
            new_intervals[self.interval_index].days_of_week = days
            self.coordinator.data.schedule_intervals_to_apply = new_intervals
