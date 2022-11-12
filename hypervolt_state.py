import dataclasses
from typing import Dict, Any


@dataclasses.dataclass
class HypervoltDeviceState:
    is_charging: bool = property(lambda self: self.state["is_charging"])

    def __init__(self, state: dict[str, Any]) -> None:
        self.state = state
