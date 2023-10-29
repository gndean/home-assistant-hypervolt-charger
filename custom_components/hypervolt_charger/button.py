import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.components.button import ButtonEntity
from typing import Any

from .hypervolt_update_coordinator import HypervoltUpdateCoordinator
from .hypervolt_entity import HypervoltEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    _LOGGER.debug("Button async_setup_entry enter")

    coordinator: HypervoltUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([HypervoltApplyScheduleButton(coordinator)])


class HypervoltApplyScheduleButton(HypervoltEntity, ButtonEntity):
    @property
    def unique_id(self):
        return super().unique_id + "_apply_schedule"

    @property
    def name(self):
        return super().name + " Apply Schedule"

    async def async_press(self) -> None:
        """Write the pending schedule to the API"""
        _LOGGER.info("Apply Schedule button pressed")

        # Remove any new intervals that have no start or end time, or the same start and end time
        self._hypervolt_coordinator.data.schedule_intervals_to_apply = [
            interval for interval in self._hypervolt_coordinator.data.schedule_intervals_to_apply if interval and interval.start_time and interval.end_time and interval.start_time != interval.end_time]

        _LOGGER.info(
            f"Setting {len(self._hypervolt_coordinator.data.schedule_intervals_to_apply)} schedule intervals")

        # Now set the new schedule back to the API
        await self._hypervolt_coordinator.api.set_schedule(
            self._hypervolt_coordinator.api_session,
            self._hypervolt_coordinator.data.activation_mode,
            self._hypervolt_coordinator.data.schedule_intervals_to_apply,
            self._hypervolt_coordinator.data.schedule_type,
            self._hypervolt_coordinator.data.schedule_tz
        )

        _LOGGER.info("Schedule applied. Reading back from API")

        # Read back schedule from API so that we're synced with the API
        await self._hypervolt_coordinator.force_update()

        _LOGGER.info(
            f"Read back {len(self._hypervolt_coordinator.data.schedule_intervals)} schedule intervals")
