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


class TestLedBrightnessLastNonZero(unittest.TestCase):
    def test_update_on_non_zero(self):
        self.assertEqual(
            _led.update_last_non_zero(previous_last_non_zero=25, current_percent=50),
            50,
        )

    def test_ignore_zero(self):
        self.assertEqual(
            _led.update_last_non_zero(previous_last_non_zero=25, current_percent=0),
            25,
        )

    def test_ignore_none(self):
        self.assertEqual(
            _led.update_last_non_zero(previous_last_non_zero=25, current_percent=None),
            25,
        )

    def test_clamps_input(self):
        self.assertEqual(
            _led.update_last_non_zero(previous_last_non_zero=None, current_percent=999),
            100,
        )
        self.assertEqual(
            _led.update_last_non_zero(previous_last_non_zero=25, current_percent=-10),
            25,
        )
