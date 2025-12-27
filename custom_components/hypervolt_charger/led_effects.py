"""Load LED effect definitions for the Hypervolt Charger integration.

This module provides a simple drop-in mechanism for additional LED effects.
To add an effect, place a JSON file in the `led_effects/` folder.

Supported file format:
- A JSON-RPC style payload (like captured from the Hypervolt app) that contains
  `params.effect_name` and optionally `params.leds`.
- Optional top-level `label` to control how the effect appears in the UI.

Example:
{
  "label": "My Effect",
  "method": "sync.apply",
  "params": {
    "effect_name": "steady_array",
    "leds": [{"r": 1.0, "g": 0.0, "b": 0.0}, ...]
  }
}
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from pathlib import Path
from typing import Any

import aiofiles

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


def _normalize_led_entry(entry: dict[str, Any]) -> dict[str, float] | None:
    try:
        r = float(entry["r"])
        g = float(entry["g"])
        b = float(entry["b"])
    except (KeyError, TypeError, ValueError):
        return None

    # Keep values as-is (Hypervolt payloads use floats in [0.0, 1.0]).
    return {"r": r, "g": g, "b": b}


def _parse_definition(
    path: Path, payload: dict[str, Any]
) -> LedEffectDefinition | None:
    params = payload.get("params")
    if not isinstance(params, dict):
        return None

    effect_name = params.get("effect_name")
    if not isinstance(effect_name, str) or not effect_name:
        return None

    label = payload.get("label")
    if not isinstance(label, str) or not label:
        label = _label_from_filename(path)

    leds_raw = params.get("leds")
    if leds_raw is None:
        return LedEffectDefinition(label=label, effect_name=effect_name, leds=None)

    if not isinstance(leds_raw, list):
        return None

    leds: list[dict[str, float]] = []
    for item in leds_raw:
        if not isinstance(item, dict):
            return None
        normalized = _normalize_led_entry(item)
        if normalized is None:
            return None
        leds.append(normalized)

    return LedEffectDefinition(label=label, effect_name=effect_name, leds=leds)


async def async_load_led_effect_definitions(
    effects_dir: Path,
) -> dict[str, LedEffectDefinition]:
    """Load LED effect definitions from the given directory."""

    if not effects_dir.exists() or not effects_dir.is_dir():
        return {}

    definitions: dict[str, LedEffectDefinition] = {}

    for path in sorted(effects_dir.glob("*.json")):
        try:
            async with aiofiles.open(path, "r", encoding="utf-8") as f:
                raw = await f.read()
            payload = json.loads(raw)
        except Exception as exc:  # noqa: BLE001 - best-effort loading of user files
            _LOGGER.warning("Failed to read LED effect file %s: %s", path.name, exc)
            continue

        if not isinstance(payload, dict):
            _LOGGER.warning(
                "Ignoring LED effect file %s: expected JSON object", path.name
            )
            continue

        definition = _parse_definition(path, payload)
        if definition is None:
            _LOGGER.warning("Ignoring LED effect file %s: invalid format", path.name)
            continue

        # Later files with same label override earlier ones.
        definitions[definition.label] = definition

    return definitions
