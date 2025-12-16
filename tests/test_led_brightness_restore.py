import unittest

import importlib.util
from pathlib import Path


def _load_led_brightness_module():
    module_path = (
        Path(__file__).resolve().parents[1]
        / "custom_components"
        / "hypervolt_charger"
        / "led_brightness.py"
    )
    spec = importlib.util.spec_from_file_location("led_brightness", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_led = _load_led_brightness_module()


class TestLedBrightnessRestore(unittest.TestCase):
    def test_turn_on_without_brightness_restores_last_non_zero(self):
        self.assertEqual(
            _led.choose_turn_on_percent(brightness=None, last_non_zero_brightness_pct=25),
            25,
        )

    def test_turn_on_without_brightness_defaults_to_100(self):
        self.assertEqual(
            _led.choose_turn_on_percent(brightness=None, last_non_zero_brightness_pct=None),
            100,
        )

    def test_turn_on_with_brightness_uses_mapping(self):
        # 255 => 100%
        self.assertEqual(
            _led.choose_turn_on_percent(brightness=255, last_non_zero_brightness_pct=25),
            100,
        )

    def test_turn_on_with_brightness_zero_returns_zero(self):
        self.assertEqual(
            _led.choose_turn_on_percent(brightness=0, last_non_zero_brightness_pct=25),
            0,
        )
