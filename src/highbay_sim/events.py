"""Immutable simulation events, the only way consumers observe a run."""

from dataclasses import dataclass
from typing import Literal

EventKind = Literal[
    "order_arrived",
    "order_waiting_for_cell",
    "order_queued",
    "order_unfulfillable",
    "order_started",
    "activity_started",
    "load_picked",
    "load_set",
    "order_completed",
]
Activity = Literal["moving_empty", "moving_loaded", "handling"]
OrderType = Literal["storage", "retrieval"]
Location = tuple[int, int, int, int]
"""A storage cell as (aisle, rack, bay, level)."""
Position = tuple[float, float]
"""A crane position in an aisle as (horizontal_m, vertical_m)."""


@dataclass(frozen=True, slots=True)
class SimulationEvent:
    time_s: float
    sequence: int
    kind: EventKind
    order_id: str
    order_type: OrderType
    crane: int | None = None
    location: Location | None = None
    """The storage cell involved; None when a load moves at a transfer point."""
    activity: Activity | None = None
    end_s: float | None = None
    """When an activity_started event's activity ends, which may be after the run."""
    start_position: Position | None = None
    """Where a movement starts; None unless this event starts a movement."""
    target_position: Position | None = None
    """Where a movement ends; None unless this event starts a movement."""
