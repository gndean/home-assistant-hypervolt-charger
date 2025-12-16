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


class TestLedBrightnessMapping(unittest.TestCase):
    def test_percent_to_ha_brightness_none(self):
        self.assertIsNone(_led.percent_to_ha_brightness(None))

    def test_percent_to_ha_brightness_bounds(self):
        self.assertEqual(_led.percent_to_ha_brightness(0), 0)
        self.assertEqual(_led.percent_to_ha_brightness(100), 255)

    def test_ha_brightness_to_percent_none(self):
        self.assertIsNone(_led.ha_brightness_to_percent(None))

    def test_ha_brightness_to_percent_bounds(self):
        self.assertEqual(_led.ha_brightness_to_percent(0), 0)
        self.assertEqual(_led.ha_brightness_to_percent(255), 100)

    def test_ha_brightness_to_percent_never_zero_when_on(self):
        # Any non-zero HA brightness must map to at least 1%.
        self.assertGreaterEqual(_led.ha_brightness_to_percent(1), 1)

    def test_ratio_to_percent(self):
        self.assertIsNone(_led.ratio_to_percent(None))
        self.assertEqual(_led.ratio_to_percent(0.0), 0)
        self.assertEqual(_led.ratio_to_percent(1.0), 100)
        self.assertEqual(_led.ratio_to_percent(0.25), 25)
