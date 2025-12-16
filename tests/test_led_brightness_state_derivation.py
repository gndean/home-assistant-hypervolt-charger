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


class TestLedBrightnessStateDerivation(unittest.TestCase):
    def test_ratio_none(self):
        self.assertIsNone(_led.ratio_to_percent(None))
        self.assertIsNone(_led.ratio_to_ha_brightness(None))

    def test_ratio_bounds(self):
        self.assertEqual(_led.ratio_to_percent(0.0), 0)
        self.assertEqual(_led.ratio_to_percent(1.0), 100)

    def test_ratio_midpoint(self):
        self.assertEqual(_led.ratio_to_percent(0.5), 50)
        self.assertEqual(_led.ratio_to_ha_brightness(0.5), round(0.5 * 255))

    def test_ratio_clamps(self):
        self.assertEqual(_led.ratio_to_percent(-1.0), 0)
        self.assertEqual(_led.ratio_to_percent(2.0), 100)
