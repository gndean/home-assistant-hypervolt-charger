import dataclasses
import logging
from typing import Optional
from .hypervolt_state import HypervoltDeviceState

import aiohttp

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class HypervoltApiClientConfig:
    username: str
    password: str
    session: Optional[aiohttp.ClientSession] = None


class HypervoltApiClient:
    @staticmethod
    def from_config(config: HypervoltApiClientConfig) -> "HypervoltApiClient":
        return HypervoltApiClient(config)

    def __init__(self, config):
        self.config = config

    async def login(self) -> bool:
        # await self.client.login()
        return True

    async def get_state(self) -> HypervoltDeviceState:
        state_dict = {"is_charging": False}
        return HypervoltDeviceState(state=state_dict)

    # async def on(self) -> bool:
    #     return await self.__set_device_state(SwitchParams(True))

    # async def off(self) -> bool:
    #     return await self.__set_device_state(SwitchParams(False))

    # async def set_brightness(self, brightness: int) -> bool:
    #     return await self.__set_device_state(LightParams(brightness=brightness))

    # async def set_color_temperature(self, color_temperature: int) -> bool:
    #     return await self.__set_device_state(
    #         LightParams(color_temperature=color_temperature)
    #     )

    # async def set_hue_saturation(self, hue: int, saturation: int) -> bool:
    #     return await self.__set_device_state(
    #         LightParams(hue=hue, saturation=saturation)
    #     )

    # async def set_light_effect(self, effect: LightEffect) -> bool:
    #     effect_params = LightEffectParams(
    #         enable=1, name=effect.name, brightness=100, display_colors=effect.colors
    #     )
    #     return await self.__set_device_state(LightParams(effect=effect_params))

    # async def __set_device_state(self, device_params: DeviceInfoParams) -> bool:
    #     try:
    #         await self.client.set_device_state(device_params, self.TERMINAL_UUID)
    #         return True
    #     except Exception as e:
    #         logger.error(e)
    #         return False

    # async def __get_energy_usage(self) -> Optional[EnergyInfo]:
    #     try:
    #         return EnergyInfo(
    #             await self.client.send_tapo_request(GetEnergyUsageMethod(None))
    #         )
    #     except (Exception,):
    #         return None
