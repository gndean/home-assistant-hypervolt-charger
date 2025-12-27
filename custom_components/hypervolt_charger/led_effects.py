"""Load LED effect definitions for the Hypervolt Charger integration.

This module provides a simple drop-in mechanism for additional LED effects.
To add an effect, place a definition file in the `led_effects/` folder.

Example YAML file:

name: Peace
default_colour: "#0057B8"
segments:
  - colour: "#FFD600"
    ranges:
      - [15, 32]
      - [39, 42]
  - colour: "#80965C"
    indices: [14, 33]
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any

import aiofiles
import yaml

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class LedEffectDefinition:
    """A single LED effect definition."""

    label: str
    effect_name: str
    leds: list[dict[str, float]] | None = None


def _label_from_filename(path: Path) -> str:
    stem = path.stem.replace("_", " ").replace("-", " ").strip()
    return " ".join(word.capitalize() for word in stem.split())


def _parse_hex_colour(value: Any) -> dict[str, float] | None:
    if not isinstance(value, str):
        return None

    text = value.strip()
    if text.startswith("#"):
        text = text[1:]

    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)

    if len(text) != 6:
        return None

    try:
        r = int(text[0:2], 16)
        g = int(text[2:4], 16)
        b = int(text[4:6], 16)
    except ValueError:
        return None

    return {"r": r / 255.0, "g": g / 255.0, "b": b / 255.0}


def _build_leds_from_segments(params: dict[str, Any]) -> list[dict[str, float]] | None:
    led_count_raw = params.get("led_count", 51)
    if not isinstance(led_count_raw, int) or led_count_raw <= 0:
        return None

    default = _parse_hex_colour(params.get("default_colour", "#000000"))
    if default is None:
        return None

    leds: list[dict[str, float]] = [default.copy() for _ in range(led_count_raw)]

    segments = params.get("segments")
    if not isinstance(segments, list) or not segments:
        return None

    for segment in segments:
        if not isinstance(segment, dict):
            return None

        colour = _parse_hex_colour(segment.get("colour"))
        if colour is None:
            return None

        indices: set[int] = set()

        indices_raw = segment.get("indices")
        if indices_raw is not None:
            if not isinstance(indices_raw, list) or not all(
                isinstance(i, int) for i in indices_raw
            ):
                return None
            indices.update(indices_raw)

        range_raw = segment.get("range")
        if range_raw is not None:
            if (
                not isinstance(range_raw, list)
                or len(range_raw) != 2
                or not all(isinstance(i, int) for i in range_raw)
            ):
                return None
            start, end = range_raw
            if start > end:
                start, end = end, start
            indices.update(range(start, end + 1))

        ranges_raw = segment.get("ranges")
        if ranges_raw is not None:
            if not isinstance(ranges_raw, list):
                return None
            for r in ranges_raw:
                if (
                    not isinstance(r, list)
                    or len(r) != 2
                    or not all(isinstance(i, int) for i in r)
                ):
                    return None
                start, end = r
                if start > end:
                    start, end = end, start
                indices.update(range(start, end + 1))

        if not indices:
            return None

        for index in indices:
            if not 0 <= index < led_count_raw:
                return None
            leds[index] = colour

    return leds


def _parse_definition(
    path: Path, payload: dict[str, Any]
) -> LedEffectDefinition | None:
    params = payload

    label = payload.get("name")
    if not isinstance(label, str) or not label:
        label = _label_from_filename(path)

    colours_raw = params.get("colours")
    if colours_raw is not None:
        if not isinstance(colours_raw, list):
            return None

        leds: list[dict[str, float]] = []
        for item in colours_raw:
            led = _parse_hex_colour(item)
            if led is None:
                return None
            leds.append(led)

        return LedEffectDefinition(label=label, effect_name="steady_array", leds=leds)

    if params.get("segments") is not None:
        leds = _build_leds_from_segments(params)
        if leds is None:
            return None
        return LedEffectDefinition(label=label, effect_name="steady_array", leds=leds)

    return None


async def async_load_led_effect_definitions(
    effects_dir: Path,
) -> dict[str, LedEffectDefinition]:
    """Load LED effect definitions from the given directory."""

    if not effects_dir.exists() or not effects_dir.is_dir():
        return {}

    definitions: dict[str, LedEffectDefinition] = {}

    paths = [*effects_dir.glob("*.yaml"), *effects_dir.glob("*.yml")]

    for path in sorted(paths):
        try:
            async with aiofiles.open(path, "r", encoding="utf-8") as f:
                raw = await f.read()

            payload = yaml.safe_load(raw)
        except Exception as exc:  # noqa: BLE001 - best-effort loading of user files
            _LOGGER.error("Failed to read LED effect file %s: %s", path.name, exc)
            continue

        if not isinstance(payload, dict):
            _LOGGER.error("Ignoring LED effect file %s: expected object", path.name)
            continue

        definition = _parse_definition(path, payload)
        if definition is None:
            _LOGGER.error("Ignoring LED effect file %s: invalid format", path.name)
            continue

        # Later files with same label override earlier ones.
        definitions[definition.label] = definition

    return definitions
