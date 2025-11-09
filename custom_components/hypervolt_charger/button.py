"""Button platform for Hypervolt Charger integration."""

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .hypervolt_entity import HypervoltEntity
from .hypervolt_update_coordinator import HypervoltUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up Hypervolt button from a config entry."""
    _LOGGER.debug("Button async_setup_entry enter")

    coordinator: HypervoltUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([HypervoltApplyScheduleButton(coordinator)])


class HypervoltApplyScheduleButton(HypervoltEntity, ButtonEntity):
    """Button to apply pending schedule to the Hypervolt charger."""

    @property
    def unique_id(self):
        """Return unique ID for the button."""
        return super().unique_id + "_apply_schedule"

    @property
    def name(self):
        """Return name of the button."""
        return super().name + " Apply Schedule"

    async def async_press(self) -> None:
        """Write the pending schedule to the API."""
        _LOGGER.info("Apply Schedule button pressed")

        if self.coordinator.data.schedule_intervals_to_apply:
            # Remove any new intervals that have no start or end time, or the same start and end time
            self.coordinator.data.schedule_intervals_to_apply = [
                interval
                for interval in self.coordinator.data.schedule_intervals_to_apply
                if interval
                and interval.start_time
                and interval.end_time
                and interval.start_time != interval.end_time
            ]

            _LOGGER.info(
                "Setting %s schedule intervals",
                len(self.coordinator.data.schedule_intervals_to_apply),
            )

            # Now set the new schedule back to the API
            if self.coordinator.api_session is None:
                _LOGGER.error("API session is not available")
                return

            await self.coordinator.api.set_schedule(
                self.coordinator.api_session,
                self.coordinator.data.activation_mode,
                self.coordinator.data.schedule_intervals_to_apply,
                self.coordinator.data.schedule_type,
                self.coordinator.data.schedule_tz,
            )

            _LOGGER.info("Schedule applied. Reading back from API")

            # Read back schedule from API so that we're synced with the API
            await self.coordinator.force_update()

            _LOGGER.info(
                "Read back %s schedule intervals",
                len(self.coordinator.data.schedule_intervals),
            )
        else:
            _LOGGER.warning(
                "Trying to apply schedule but there are no schedule intervals to apply"
            )
