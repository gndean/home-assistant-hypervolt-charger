from __future__ import annotations

from enum import Enum
from datetime import time


class HypervoltLockState(Enum):
    UNLOCKED = 0
    PENDING_LOCK = 1
    LOCKED = 2


class HypervoltChargeMode(Enum):
    BOOST = 0
    ECO = 1
    SUPER_ECO = 2


class HypervoltActivationMode(Enum):
    PLUG_AND_CHARGE = 0
    SCHEDULE = 1


class HypervoltReleaseState(Enum):
    # Ready to charge, waiting for schedule/solar, or car has finished charging
    DEFAULT = 0

    # User cancelled the charge via Hypervolt
    RELEASED = 1


class HypervoltDayOfWeek(Enum):
    MONDAY = 1
    TUESDAY = 2
    WEDNESDAY = 4
    THURSDAY = 8
    FRIDAY = 16
    SATURDAY = 32
    SUNDAY = 64
    ALL = 127


# The number of schedule intervals / sessions we support via the UI
NUM_SCHEDULE_INTERVALS = 4


class HypervoltScheduleInterval:
    def __init__(
        self,
        start_time: time,
        end_time: time,
        charge_mode: HypervoltChargeMode = HypervoltChargeMode.BOOST,
        days_of_week: int = HypervoltDayOfWeek.ALL,
    ) -> None:
        self.start_time = start_time
        self.end_time = end_time

        # V3 specific fields
        self.charge_mode = charge_mode
        self.days_of_week = days_of_week


class HypervoltDeviceState:
    """Class to hold current state of Hypervolt charger"""

    def __init__(self, charger_id) -> None:
        self.charger_id = charger_id
        self.is_charging = None
        self.session_id = None
        self.session_watthours = None
        self.session_currency_spent = None
        self.session_carbon_saved_grams = None
        self.max_current_milliamps = None
        self.current_session_current_milliamps = None
        self.current_session_ct_current = None
        self.current_session_ct_power = None
        self.current_session_voltage = None
        self.ev_power = None
        self.house_power = None
        self.grid_power = None
        self.generation_power = None
        self.led_brightness = None
        self.lock_state: HypervoltLockState = None
        self.charge_mode: HypervoltChargeMode = None
        self.release_state: HypervoltReleaseState = None
        self.activation_mode: HypervoltActivationMode = None
        self.schedule_intervals: list[HypervoltScheduleInterval] = None
        self.schedule_tz = None
        self.schedule_type = None

        # The schedule intervals to apply when the Apply button is pressed
        # These can be edited via the Start/End Time time entities but only
        # applied to the charger when the Apply button is pressed
        self.schedule_intervals_to_apply: list[HypervoltScheduleInterval] = None

        # Not taken directly from the Hypervolt API but instead a calculated field
        # to be exposed as a strictly TOTAL_INCREASING sensor class to allow
        # energy calculations via Home Assistant
        # Resets to 0 when a new session is created else is the max(session_watthours) during the session
        self.session_watthours_total_increasing = None

        # A derived field, calculated from differentiating session_watthours_total_increasing
        # over a time window and estimating the current charger output power over that time.
        # In Watts
        self.current_session_power = 0
