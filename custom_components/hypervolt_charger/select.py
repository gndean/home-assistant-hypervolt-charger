from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .hypervolt_update_coordinator import HypervoltUpdateCoordinator
from .hypervolt_entity import HypervoltEntity
from .hypervolt_device_state import HypervoltChargeMode, HypervoltActivationMode
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: HypervoltUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [ChargeModeSelect(coordinator), ActivationModeSelect(coordinator)]
    )


class ChargeModeSelect(HypervoltEntity, SelectEntity):
    # TODO: Get these from translations
    _CHARGE_MODE_STRINGS = ["Boost", "Eco", "Super Eco"]

    @property
    def name(self) -> str:
        return super().name + " Charge Mode"

    @property
    def unique_id(self) -> str:
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
                await self._hypervolt_coordinator.api.v2_set_schedule(
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
