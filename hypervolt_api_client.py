import dataclasses
import json
import logging
from typing import Optional

from homeassistant.exceptions import HomeAssistantError
from .hypervolt_state import HypervoltDeviceState

import aiohttp

logger = logging.getLogger(__name__)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class HypervoltApiClient:
    def __init__(self, username, password, charger_id=None):
        """Set charger_id if known, or None during config, to allow chargers to be enumerated after login()"""
        self.username = username
        self.password = password
        self.charger_id = charger_id
        self.is_logged_in = False
        self.session = aiohttp.ClientSession()

    async def login(self):
        """Attempt to log in using credentials from config. Raises InvalidAuth or CannotConnect on failure"""

        self.is_logged_in = False

        try:
            async with self.session.get(
                "https://api.hypervolt.co.uk/login-url"
            ) as response:

                login_base_url = json.loads(await response.text())["login"]

                print(f"Loading URL: {login_base_url}")

                # This will cause a 302 redirect to a new URL that loads a login form
                async with self.session.get(login_base_url) as response:
                    if response.status == 200:
                        login_form_url = response.url
                        state = login_form_url.query["state"]
                        login_form_data = f"state={state}&username={self.username}&password={self.password}&action=default"
                        self.session.headers.update(
                            {"content-type": "application/x-www-form-urlencoded"}
                        )
                        async with self.session.post(
                            login_form_url,
                            headers=self.session.headers,
                            data=login_form_data,
                        ) as response:
                            if response.status == 200:
                                print("HypervoltApiClient logged in!")
                                self.is_logged_in = True
                                return True

                            elif response.status >= 400 and response.status < 500:
                                print(
                                    f"Authentication error when trying to log in, status code: {response.status}"
                                )
                                raise InvalidAuth
                            else:
                                response_text = await response.text()
                                print(
                                    f"Error: unable to get charger, status: {response.status}, {response_text}"
                                )
                                raise CannotConnect
                    else:
                        response_text = await response.text()
                        print(
                            f"Error: unable to login, status: {response.status}, {response_text}"
                        )
                        raise InvalidAuth

        except InvalidAuth as exc:
            raise InvalidAuth from exc
        except Exception as exc:
            raise CannotConnect from exc

    async def get_state(self) -> HypervoltDeviceState:
        d = {}
        d["charger_id"] = self.charger_id
        d["is_charging"] = False

        state = HypervoltDeviceState(d)
        return state

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
