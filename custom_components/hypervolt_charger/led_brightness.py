"""Pure helpers for Hypervolt LED brightness.

These helpers are intentionally Home Assistant-agnostic so they can be unit tested
without requiring Home Assistant to be installed.
"""

from __future__ import annotations


def clamp_int(value: int, min_value: int, max_value: int) -> int:
    return max(min_value, min(max_value, value))


def clamp_percent(percent: int) -> int:
    return clamp_int(percent, 0, 100)


def percent_to_ha_brightness(percent: int | None) -> int | None:
    """Convert a percent value (0-100) to HA brightness (0-255)."""
    if percent is None:
        return None

    percent = clamp_percent(int(percent))
    return round(percent / 100 * 255)


def ha_brightness_to_percent(brightness: int | None) -> int | None:
    """Convert HA brightness (0-255) to percent (0-100).

    Ensures brightness > 0 never maps to 0%.
    """
    if brightness is None:
        return None

    brightness = clamp_int(int(brightness), 0, 255)
    if brightness == 0:
        return 0

    percent = round(brightness / 255 * 100)
    if percent == 0:
        percent = 1
    return clamp_percent(percent)


def ratio_to_percent(ratio: float | None) -> int | None:
    """Convert Hypervolt brightness ratio (0.0-1.0) to percent (0-100)."""
    if ratio is None:
        return None

    if ratio <= 0:
        return 0
    if ratio >= 1:
        return 100

    return clamp_percent(round(ratio * 100))


def choose_turn_on_percent(
    *,
    brightness: int | None,
    last_non_zero_brightness_pct: int | None,
    default_percent: int = 100,
) -> int:
    """Choose the target percent for a turn_on call.

    Rules:
    - If brightness is provided, map it to percent.
    - If brightness is missing, use last_non_zero_brightness_pct.
    - If still unknown, use default_percent.
    """
    if brightness is None:
        if last_non_zero_brightness_pct is not None:
            return clamp_percent(int(last_non_zero_brightness_pct))
        return clamp_percent(int(default_percent))

    percent = ha_brightness_to_percent(brightness)
    return int(percent or 0)
