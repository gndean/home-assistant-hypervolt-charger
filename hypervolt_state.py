import dataclasses
from typing import Dict, Any


@dataclasses.dataclass
class HypervoltDeviceState:
    charger_id: str = property(lambda self: self.state["charger_id"])
    is_charging: bool = property(lambda self: self.state["is_charging"])

    def __init__(self, state: Dict[str, Any]) -> None:
        self.state = state
