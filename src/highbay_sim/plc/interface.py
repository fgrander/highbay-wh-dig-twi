"""How the signal list appears in the PLC, as in contracts/plc-interface.md."""

from dataclasses import dataclass
from typing import Final

from highbay_sim.config import WarehouseDefinition
from highbay_sim.plc.link import PlcType
from highbay_sim.signals import SIGNALS, SignalDefinition

INTERFACE_VERSION: Final = 1
BLOCK: Final = "HB_Interface"

_MODEL_DIRECTIONS: Final = ("order_handling_to_controller", "plant_to_controller")
MODEL_SIGNALS: Final = tuple(s for s in SIGNALS if s.direction in _MODEL_DIRECTIONS)
PLC_SIGNALS: Final = tuple(s for s in SIGNALS if s.direction not in _MODEL_DIRECTIONS)

INTERFACE_VERSION_TAG: Final = f"{BLOCK}.interface_version"
SIGNAL_LIST_VERSION_TAG: Final = f"{BLOCK}.signal_list_version"
CRANE_COUNT_TAG: Final = f"{BLOCK}.crane_count"
HEARTBEAT_TAG: Final = f"{BLOCK}.plc_heartbeat"
RESET_REQUEST_TAG: Final = f"{BLOCK}.reset_request"
RESET_DONE_TAG: Final = f"{BLOCK}.reset_done"


def plc_type_of(signal: SignalDefinition) -> PlcType:
    if signal.type == "number":
        return "LReal"
    return "DInt" if signal.type == "integer" else "Bool"


@dataclass(frozen=True)
class PlcInterface:
    crane_count: int

    def __post_init__(self) -> None:
        if self.crane_count < 1:
            raise ValueError(f"crane_count must be at least 1, not {self.crane_count}")

    @classmethod
    def for_warehouse(cls, warehouse: WarehouseDefinition) -> "PlcInterface":
        return cls(warehouse.layout.aisle_count)

    @property
    def aisles(self) -> range:
        return range(1, self.crane_count + 1)

    @property
    def header_tags(self) -> dict[str, str]:
        return {
            INTERFACE_VERSION_TAG: "DInt",
            SIGNAL_LIST_VERSION_TAG: "DInt",
            CRANE_COUNT_TAG: "DInt",
            HEARTBEAT_TAG: "DInt",
            RESET_REQUEST_TAG: "Bool",
            RESET_DONE_TAG: "Bool",
        }

    @property
    def model_tags(self) -> tuple[str, ...]:
        return tuple(self.tag(a, s.name) for a in self.aisles for s in MODEL_SIGNALS)

    @property
    def plc_tags(self) -> tuple[str, ...]:
        return tuple(self.tag(a, s.name) for a in self.aisles for s in PLC_SIGNALS)

    def tag(self, aisle: int, signal: str) -> str:
        return f"{BLOCK}.crane_{aisle}.{signal}"

    def tag_types(self) -> dict[str, str]:
        crane_tags = {
            self.tag(aisle, signal.name): plc_type_of(signal)
            for aisle in self.aisles
            for signal in SIGNALS
        }
        return {**self.header_tags, **crane_tags}
