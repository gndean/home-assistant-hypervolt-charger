"""Light platform for Hypervolt Charger integration.

Exposes the charger LED brightness as a Home Assistant light with on/off + dimming.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN
from .led_brightness import (
    choose_turn_on_percent,
    clamp_percent,
    percent_to_ha_brightness,
    ratio_to_percent,
    update_last_non_zero,
)
from .hypervolt_entity import HypervoltEntity
from .hypervolt_update_coordinator import HypervoltUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Hypervolt light entities from a config entry."""
    coordinator: HypervoltUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([HypervoltLedBrightnessLight(coordinator)])


class HypervoltLedBrightnessLight(HypervoltEntity, RestoreEntity, LightEntity):
    """Light entity for charger LED brightness."""

    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_color_mode = ColorMode.BRIGHTNESS

    def __init__(self, coordinator: HypervoltUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._last_non_zero_brightness_pct: int | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        # Restore the last non-zero brightness preference (stored as percent).
        # Do not restore actual brightness state here; state comes from coordinator.
        last_state = await self.async_get_last_state()
        if last_state is not None:
            restored = last_state.attributes.get("last_non_zero_brightness_pct")
            if restored is not None:
                try:
                    restored_int = int(restored)
                except (TypeError, ValueError):
                    restored_int = None
                if restored_int is not None and 1 <= restored_int <= 100:
                    self._last_non_zero_brightness_pct = restored_int

    def _handle_coordinator_update(self) -> None:
        # Track "last non-zero" from any confirmed coordinator update.
        percent = ratio_to_percent(self.coordinator.data.led_brightness)
        self._last_non_zero_brightness_pct = update_last_non_zero(
            previous_last_non_zero=self._last_non_zero_brightness_pct,
            current_percent=percent,
        )

        super()._handle_coordinator_update()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {}
        if self._last_non_zero_brightness_pct is not None:
            attrs["last_non_zero_brightness_pct"] = self._last_non_zero_brightness_pct
        return attrs

    @property
    def brightness(self) -> int | None:
        percent = ratio_to_percent(self.coordinator.data.led_brightness)
        return percent_to_ha_brightness(percent)

    @property
    def is_on(self) -> bool | None:
        percent = ratio_to_percent(self.coordinator.data.led_brightness)
        if percent is None:
            return None
        return percent > 0

    def _get_turn_on_percent(self, brightness: int | None) -> int:
        return choose_turn_on_percent(
            brightness=brightness,
            last_non_zero_brightness_pct=self._last_non_zero_brightness_pct,
            default_percent=100,
        )

    async def _async_set_led_brightness_percent(self, percent: int) -> None:
        percent = clamp_percent(int(percent))
        if self.coordinator.api.websocket_sync is None:
            _LOGGER.error(
                "Cannot set LED brightness to %s%% because sync websocket is not connected",
                percent,
            )
            raise HomeAssistantError(
                "Cannot set Hypervolt LED brightness: sync websocket not connected"
            )

        try:
            await self.coordinator.api.set_led_brightness(float(percent))
        except Exception as exc:
            _LOGGER.error(
                "Failed to set Hypervolt LED brightness to %s%%: %s",
                percent,
                exc,
            )
            raise HomeAssistantError(
                "Failed to set Hypervolt LED brightness"
            ) from exc

    async def async_turn_on(self, **kwargs: Any) -> None:
        percent = self._get_turn_on_percent(kwargs.get(ATTR_BRIGHTNESS))
        if percent <= 0:
            await self.async_turn_off()
            return

        await self._async_set_led_brightness_percent(percent)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_set_led_brightness_percent(0)

    async def async_toggle(self, **kwargs: Any) -> None:
        if self.is_on:
            await self.async_turn_off(**kwargs)
        else:
            await self.async_turn_on(**kwargs)

    @property
    def unique_id(self) -> str:
        return super().unique_id + "_led_brightness_light"

    @property
    def name(self) -> str:
        return super().name + " LED Brightness"

