from enum import Enum


class HypervoltLockState(Enum):
    UNLOCKED = 0
    PENDING_LOCK = 1
    LOCKED = 2


class HypervoltChargeMode(Enum):
    BOOST = 0
    ECO = 1
    SUPER_ECO = 2


class HypervoltDeviceState:
    """Class to hold current state of Hypervolt charger"""

    def __init__(self):
        self.charger_id = None
        self.is_charging = None
        self.last_session_id = None
        self.last_session_watthours = None
        self.last_session_currency_spent = None
        self.last_session_carbon_saved_grams = None
        self.max_current_milliamps = None
        self.current_session_current_milliamps = None
        self.current_session_ct_current = None
        self.current_session_ct_power = None
        self.current_session_voltage = None
        self.led_brightness = None
        self.lock_state = None
        self.charge_mode = None
