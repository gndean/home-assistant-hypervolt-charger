"""LED light entities for the Hypervolt Charger integration."""

from __future__ import annotations

import logging

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntityFeature,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .hypervolt_entity import HypervoltEntity
from .hypervolt_update_coordinator import HypervoltUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

EFFECT_NO_EFFECT = "No effect"
EFFECT_STATIC = "Static"
EFFECT_PARTY = "Party"
EFFECT_HALLOWEEN = "Halloween"
EFFECT_RED_ALERT = "Red alert"
EFFECT_TURBO_BOOST = "Turbo boost"
EFFECT_CHRISTMAS = "Christmas"

EFFECT_LIST: list[str] = [
    EFFECT_NO_EFFECT,
    EFFECT_STATIC,
    EFFECT_PARTY,
    EFFECT_HALLOWEEN,
    EFFECT_RED_ALERT,
    EFFECT_TURBO_BOOST,
    EFFECT_CHRISTMAS,
]

_EFFECT_NAME_MAP: dict[str, str] = {
    # These are derived from observed payloads and a best-effort naming convention.
    EFFECT_PARTY: "party_mode",
    EFFECT_HALLOWEEN: "halloween",
    EFFECT_RED_ALERT: "red_alert",
    EFFECT_TURBO_BOOST: "knight_rider",
    EFFECT_CHRISTMAS: "christmas",
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: HypervoltUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([HypervoltLedLightEntity(coordinator)])


class HypervoltLedLightEntity(HypervoltEntity, LightEntity):
    """Light entity representing Hypervolt LEDs."""

    _attr_supported_color_modes = {ColorMode.RGB}
    _attr_color_mode = ColorMode.RGB
    _attr_effect_list = EFFECT_LIST
    _attr_supported_features = LightEntityFeature.EFFECT

    @property
    def effect_list(self) -> list[str] | None:
        # Base effects (requested feature list) + any drop-in effects loaded from files.
        additional = [
            label
            for label in self.coordinator.led_effect_definitions
            if label not in EFFECT_LIST
        ]
        return [*EFFECT_LIST, *additional]

    @property
    def unique_id(self) -> str:
        return f"{super().unique_id}_led"

    @property
    def name(self) -> str:
        return f"{super().name} LED"

    @property
    def is_on(self) -> bool:
        # "Off" means brightness is 0.
        return bool(self.coordinator.data.led_brightness)

    @property
    def brightness(self) -> int | None:
        if self.coordinator.data.led_brightness is None:
            return None
        value = int(round(self.coordinator.data.led_brightness * 255))
        return max(0, min(255, value))

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        return self.coordinator.data.led_static_rgb_color

    @property
    def effect(self) -> str | None:
        if self.coordinator.data.led_effect_name == "none":
            return EFFECT_NO_EFFECT

        if (label := self.coordinator.data.led_effect_label) is not None:
            return label

        effect_name = self.coordinator.data.led_effect_name

        # We use steady_array for Static and Peace. If we don't know which
        # preset was last used (e.g., after restart), show Static.
        if effect_name == "steady_array":
            return EFFECT_STATIC

        for label, api_name in _EFFECT_NAME_MAP.items():
            if api_name == effect_name:
                return label

        return effect_name

    async def async_turn_off(self, **kwargs) -> None:
        # Turning the light off sets brightness to 0.
        if (
            self.coordinator.data.led_brightness
            and self.coordinator.data.led_brightness > 0
        ):
            self.coordinator.data.led_last_nonzero_brightness = (
                self.coordinator.data.led_brightness
            )

        await self.coordinator.api.set_led_brightness(0)
        self.coordinator.data.led_brightness = 0.0
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs) -> None:
        requested_effect = kwargs.get(ATTR_EFFECT)
        rgb = kwargs.get(ATTR_RGB_COLOR)

        # Apply effect only if explicitly requested (or if a color is set without
        # an effect, which implies Static).
        if requested_effect is not None or rgb is not None:
            effect = requested_effect or EFFECT_STATIC

            if rgb is not None:
                self.coordinator.data.led_static_rgb_color = rgb

            if effect == EFFECT_STATIC:
                await self.coordinator.api.set_led_static_rgb_color(
                    self.coordinator.data.led_static_rgb_color
                )
                self.coordinator.data.led_effect_name = "steady_array"
                self.coordinator.data.led_effect_label = EFFECT_STATIC

            elif effect == EFFECT_NO_EFFECT:
                await self.coordinator.api.set_led_effect_name("none")
                self.coordinator.data.led_effect_name = "none"
                self.coordinator.data.led_effect_label = EFFECT_NO_EFFECT

            elif (
                definition := self.coordinator.led_effect_definitions.get(effect)
            ) is not None:
                # Drop-in effect defined via `led_effects/*.json`.
                await self.coordinator.api.set_led_effect(
                    definition.effect_name,
                    definition.leds,
                )
                self.coordinator.data.led_effect_name = definition.effect_name
                self.coordinator.data.led_effect_label = definition.label

            else:
                effect_name = _EFFECT_NAME_MAP.get(effect)
                if effect_name is None:
                    _LOGGER.warning("Unknown LED effect selected: %s", effect)
                    return

                await self.coordinator.api.set_led_effect_name(effect_name)
                self.coordinator.data.led_effect_name = effect_name
                self.coordinator.data.led_effect_label = effect

        # Brightness maps to the existing brightness control (0.0-1.0 in state).
        if (brightness := kwargs.get(ATTR_BRIGHTNESS)) is None:
            # If nothing specified and we're currently off (brightness 0), restore.
            if not self.coordinator.data.led_brightness:
                brightness = int(
                    round(self.coordinator.data.led_last_nonzero_brightness * 255)
                )

        if brightness is not None:
            percent = (float(brightness) / 255.0) * 100.0
            await self.coordinator.api.set_led_brightness(percent)
            self.coordinator.data.led_brightness = float(brightness) / 255.0
            if self.coordinator.data.led_brightness > 0:
                self.coordinator.data.led_last_nonzero_brightness = (
                    self.coordinator.data.led_brightness
                )

        self.async_write_ha_state()
