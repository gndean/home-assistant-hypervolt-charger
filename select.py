from __future__ import annotations

import datetime
import json
import logging

from homeassistant.components.select import SelectEntity
from dataclasses import dataclass
from typing import Optional
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.const import PERCENTAGE

from .hypervolt_update_coordinator import HypervoltUpdateCoordinator
from .hypervolt_entity import HypervoltEntity
from .hypervolt_device_state import HypervoltChargeMode, HypervoltActivationMode
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: HypervoltUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    await coordinator.async_config_entry_first_refresh()

    async_add_entities(
        [ChargeModeSelect(coordinator), ActivationModeSelect(coordinator)]
    )


class ChargeModeSelect(HypervoltEntity, SelectEntity):
    # TODO: Get these from translations
    _CHARGE_MODE_STRINGS = ["Boost", "Eco", "Super Eco"]

    def __init__(self, coordinator):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)

    @property
    def name(self):
        return super().name + " Charge Mode"

    @property
    def unique_id(self):
        return super().unique_id + "_charge_mode"

    @property
    def options(self) -> list[str]:
        """Return a set of selectable options."""

        return self._CHARGE_MODE_STRINGS

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        charge_mode = self._hypervolt_coordinator.data.charge_mode
        if charge_mode:
            return self._CHARGE_MODE_STRINGS[charge_mode.value]
        else:
            return None

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        if option and option in self._CHARGE_MODE_STRINGS:
            await self._hypervolt_coordinator.api.set_charge_mode(
                HypervoltChargeMode(self._CHARGE_MODE_STRINGS.index(option))
            )
        else:
            _LOGGER.warning("Unknown charge mode selected: %s", option)


class ActivationModeSelect(HypervoltEntity, SelectEntity):
    # TODO: Get these from translations
    _ACTIVATION_MODE_STRINGS = ["Plug and Charge", "Schedule"]

    def __init__(self, coordinator):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)

    @property
    def name(self):
        return super().name + " Activation Mode"

    @property
    def unique_id(self):
        return super().unique_id + "activation_mode"

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
            await self._hypervolt_coordinator.api.set_schedule(
                self._hypervolt_coordinator.api_session,
                HypervoltActivationMode(self._ACTIVATION_MODE_STRINGS.index(option)),
                self._hypervolt_coordinator.data.schedule_intervals,
            )
            # Read back schedule from API so that we're up to date
            await self._hypervolt_coordinator.api.update_state_from_schedule(
                self._hypervolt_coordinator.api_session,
                self._hypervolt_coordinator.data,
            )
        else:
            _LOGGER.warning("Unknown activation mode selected: %s", option)
