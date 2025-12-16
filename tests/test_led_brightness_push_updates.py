import logging
from dataclasses import dataclass
from unittest.mock import AsyncMock, Mock

import pytest

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from custom_components.hypervolt_charger.const import DOMAIN
from custom_components.hypervolt_charger.light import HypervoltLedBrightnessLight

_LOGGER = logging.getLogger(__name__)


@dataclass
class _State:
    charger_id: str
    led_brightness: float | None


class _Api:
    def __init__(self) -> None:
        self.websocket_sync = object()
        self.set_led_brightness = AsyncMock()


@pytest.mark.asyncio
async def test_coordinator_push_update_triggers_entity_state_write(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={"charger_id": "ABC123"})
    entry.add_to_hass(hass)

    coordinator: DataUpdateCoordinator[_State] = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="hypervolt_test",
        update_method=AsyncMock(),
        config_entry=entry,
    )
    coordinator.data = _State(charger_id="ABC123", led_brightness=0.0)
    coordinator.api = _Api()

    entity = HypervoltLedBrightnessLight(coordinator)
    entity.hass = hass
    entity.async_get_last_state = AsyncMock(return_value=None)

    write_mock = Mock()
    entity.async_write_ha_state = write_mock

    await entity.async_added_to_hass()

    # Simulate websocket push -> coordinator updated data
    coordinator.async_set_updated_data(_State(charger_id="ABC123", led_brightness=0.5))

    assert write_mock.call_count == 1
    assert entity.brightness == round(0.5 * 255)
    assert entity.is_on is True
