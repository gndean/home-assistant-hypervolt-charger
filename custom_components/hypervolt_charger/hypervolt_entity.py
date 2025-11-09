"""Base entity for Hypervolt Charger integration."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .hypervolt_update_coordinator import HypervoltUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class HypervoltEntity(CoordinatorEntity[HypervoltUpdateCoordinator]):
    """Base entity for Hypervolt Charger."""

    coordinator: HypervoltUpdateCoordinator

    def __init__(self, coordinator: HypervoltUpdateCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self.coordinator.data.charger_id)},
            "name": f"Hypervolt {self.coordinator.data.charger_id}",
            "manufacturer": "Hypervolt",
        }

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return self.coordinator.data.charger_id

    @property
    def name(self) -> str:
        """Return entity name."""
        return "Hypervolt"
