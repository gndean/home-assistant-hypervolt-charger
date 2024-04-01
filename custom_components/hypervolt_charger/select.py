from __future__ import annotations

import logging

from copy import deepcopy

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .hypervolt_update_coordinator import HypervoltUpdateCoordinator
from .hypervolt_entity import HypervoltEntity
from .hypervolt_device_state import (
    HypervoltChargeMode,
    HypervoltActivationMode,
    HypervoltScheduleInterval,
    NUM_SCHEDULE_INTERVALS,
)
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: HypervoltUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [ChargeModeSelect(coordinator), ActivationModeSelect(coordinator)]

    # For V3 devices, create entities for charge mode, for each schedule interval
    if coordinator.api.get_charger_major_version() >= 3:
        for interval_index in range(NUM_SCHEDULE_INTERVALS):
            entities.append(ChargeModeSelect(coordinator, True, interval_index))

    async_add_entities(entities)


class ChargeModeSelect(HypervoltEntity, SelectEntity):
    def __init__(
        self,
        coordinator: HypervoltUpdateCoordinator,
        is_schedule_selector: bool = False,
        interval_index: int = -1,
    ) -> None:
        super(ChargeModeSelect, self).__init__(coordinator)

        self._attr_native_value = None
        self.is_schedule_selector = is_schedule_selector
        self.interval_index = interval_index

    # TODO: Get these from translations
    _CHARGE_MODE_STRINGS = ["Boost", "Eco", "Super Eco"]

    @property
    def name(self) -> str:
        if self.is_schedule_selector:
            return (
                f"{super().name} Schedule Session {self.interval_index+1} Charge Mode"
            )
        else:
            return super().name + " Charge Mode"

    @property
    def unique_id(self) -> str:
        if self.is_schedule_selector:
            return f"{super().unique_id}_schedule_session_{self.interval_index+1}_charge_mode"
        else:
            return super().unique_id + "_charge_mode"

    @property
    def options(self) -> list[str]:
        """Return a set of selectable options."""

        return self._CHARGE_MODE_STRINGS

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        if self.is_schedule_selector:
            intervals = self._hypervolt_coordinator.data.schedule_intervals_to_apply
            if (
                intervals
                and len(intervals) > self.interval_index
                and intervals[self.interval_index]
            ):
                return self._CHARGE_MODE_STRINGS[
                    intervals[self.interval_index].charge_mode.value
                ]

            return None
        else:
            charge_mode = self._hypervolt_coordinator.data.charge_mode
            if charge_mode:
                return self._CHARGE_MODE_STRINGS[charge_mode.value]
            else:
                return None

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        if option and option in self._CHARGE_MODE_STRINGS:
            if self.is_schedule_selector:
                # Set the schedule interval charge mode
                # First create an array of the max size, and fill it with the existing values
                new_intervals: list[HypervoltScheduleInterval] = [
                    None
                ] * NUM_SCHEDULE_INTERVALS
                intervals = self._hypervolt_coordinator.data.schedule_intervals_to_apply
                if intervals:
                    for i, interval in enumerate(intervals):
                        new_intervals[i] = deepcopy(interval)

                if not new_intervals[self.interval_index]:
                    new_intervals[self.interval_index] = HypervoltScheduleInterval(
                        None, None
                    )
                new_intervals[self.interval_index].charge_mode = HypervoltChargeMode(
                    self._CHARGE_MODE_STRINGS.index(option)
                )
                self._hypervolt_coordinator.data.schedule_intervals_to_apply = (
                    new_intervals
                )

            else:
                # Set the current charge mode
                await self._hypervolt_coordinator.api.set_charge_mode(
                    HypervoltChargeMode(self._CHARGE_MODE_STRINGS.index(option))
                )
        else:
            _LOGGER.warning("Unknown charge mode selected: %s", option)


class ActivationModeSelect(HypervoltEntity, SelectEntity):
    # TODO: Get these from translations
    _ACTIVATION_MODE_STRINGS = ["Plug and Charge", "Schedule"]

    @property
    def name(self) -> str:
        return super().name + " Activation Mode"

    @property
    def unique_id(self) -> str:
        return super().unique_id + "_activation_mode"

    @property
    def options(self) -> list[str]:
        """Return a set of selectable options."""

        return self._ACTIVATION_MODE_STRINGS

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        activation_mode = self._hypervolt_coordinator.data.activation_mode
        if activation_mode:
            return self._ACTIVATION_MODE_STRINGS[activation_mode.value]
        else:
            return None

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        if option and option in self._ACTIVATION_MODE_STRINGS:
            if self._hypervolt_coordinator.api.get_charger_major_version() == 2:
                await self._hypervolt_coordinator.api.set_schedule(
                    self._hypervolt_coordinator.api_session,
                    HypervoltActivationMode(
                        self._ACTIVATION_MODE_STRINGS.index(option)
                    ),
                    self._hypervolt_coordinator.data.schedule_intervals,
                    self._hypervolt_coordinator.data.schedule_type,
                    self._hypervolt_coordinator.data.schedule_tz,
                )
                # Read back schedule from API so that we're up to date
                await self._hypervolt_coordinator.api.v2_update_state_from_schedule(
                    self._hypervolt_coordinator.api_session,
                    self._hypervolt_coordinator.data,
                )
            else:
                await self._hypervolt_coordinator.api.v3_set_schedule_enabled(
                    HypervoltActivationMode(self._ACTIVATION_MODE_STRINGS.index(option))
                    == HypervoltActivationMode.SCHEDULE
                )
        else:
            _LOGGER.warning("Unknown activation mode selected: %s", option)
