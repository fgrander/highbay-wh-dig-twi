"""The signals between a controller and the plant, as in contracts/signal-list.md."""

from dataclasses import dataclass
from enum import IntEnum
from typing import Final, Literal

SIGNAL_LIST_VERSION: Final = 1

Direction = Literal[
    "order_handling_to_controller",
    "controller_to_order_handling",
    "controller_to_plant",
    "plant_to_controller",
]


class FaultCode(IntEnum):
    NONE = 0
    TARGET_OUT_OF_RANGE = 1
    CRANE_BUSY = 2
    NO_PLACE = 3
    INVALID_SIDE = 4
    NOTHING_TO_PICK = 5
    PLACE_OCCUPIED = 6
    SET_NOT_ALLOWED = 7
    CRANE_ALREADY_LOADED = 8
    CRANE_EMPTY = 9
    CONFLICTING_COMMANDS = 10


@dataclass(frozen=True, slots=True)
class Fault:
    """A command that the plant refused, and why."""

    cycle: int
    time_s: float
    crane: int
    code: FaultCode
    description: str


@dataclass(frozen=True, slots=True)
class SignalDefinition:
    name: str
    direction: Direction
    type: str
    unit: str = ""


_RISING_EDGE: Final = "boolean, rising edge"
SIGNALS: Final = (
    SignalDefinition("job_id", "order_handling_to_controller", "integer"),
    SignalDefinition("source_horizontal_m", "order_handling_to_controller", "number", "m"),
    SignalDefinition("source_vertical_m", "order_handling_to_controller", "number", "m"),
    SignalDefinition("source_side", "order_handling_to_controller", "integer"),
    SignalDefinition("destination_horizontal_m", "order_handling_to_controller", "number", "m"),
    SignalDefinition("destination_vertical_m", "order_handling_to_controller", "number", "m"),
    SignalDefinition("destination_side", "order_handling_to_controller", "integer"),
    SignalDefinition("job_done_id", "controller_to_order_handling", "integer"),
    SignalDefinition("horizontal_target_m", "controller_to_plant", "number", "m"),
    SignalDefinition("vertical_target_m", "controller_to_plant", "number", "m"),
    SignalDefinition("horizontal_start", "controller_to_plant", _RISING_EDGE),
    SignalDefinition("vertical_start", "controller_to_plant", _RISING_EDGE),
    SignalDefinition("side", "controller_to_plant", "integer"),
    SignalDefinition("pick_start", "controller_to_plant", _RISING_EDGE),
    SignalDefinition("set_start", "controller_to_plant", _RISING_EDGE),
    SignalDefinition("fault_reset", "controller_to_plant", _RISING_EDGE),
    SignalDefinition("horizontal_actual_m", "plant_to_controller", "number", "m"),
    SignalDefinition("vertical_actual_m", "plant_to_controller", "number", "m"),
    SignalDefinition("horizontal_in_position", "plant_to_controller", "boolean"),
    SignalDefinition("vertical_in_position", "plant_to_controller", "boolean"),
    SignalDefinition("handling_active", "plant_to_controller", "boolean"),
    SignalDefinition("load_present", "plant_to_controller", "boolean"),
    SignalDefinition("fault_code", "plant_to_controller", "integer"),
)


@dataclass(slots=True)
class CraneSignals:
    """The current value of every signal of one crane."""

    job_id: int = 0
    source_horizontal_m: float = 0.0
    source_vertical_m: float = 0.0
    source_side: int = 0
    destination_horizontal_m: float = 0.0
    destination_vertical_m: float = 0.0
    destination_side: int = 0
    job_done_id: int = 0
    horizontal_target_m: float = 0.0
    vertical_target_m: float = 0.0
    horizontal_start: bool = False
    vertical_start: bool = False
    side: int = 0
    pick_start: bool = False
    set_start: bool = False
    fault_reset: bool = False
    horizontal_actual_m: float = 0.0
    vertical_actual_m: float = 0.0
    horizontal_in_position: bool = False
    vertical_in_position: bool = False
    handling_active: bool = False
    load_present: bool = False
    fault_code: int = 0
