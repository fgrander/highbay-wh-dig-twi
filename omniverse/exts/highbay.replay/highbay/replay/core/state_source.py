"""The interface between state sources and the display. See contracts/state-interface.md."""

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

INTERFACE_VERSION = 2

Location = tuple[int, int, int, int]


class StateSourceError(Exception):
    """A source cannot be used. The message names the source and the problem."""


@dataclass(frozen=True, slots=True)
class WarehouseDescription:
    layout: dict[str, Any]
    crane: dict[str, Any]
    transfer_points: dict[str, Any]
    crane_start_positions: dict[str, Any]
    articles: list[str]
    run: dict[str, Any] = field(default_factory=dict)
    reported: dict[str, Any] | None = None


@dataclass(slots=True)
class LoadUnit:
    key: str
    article: int
    store_order: int | None
    retrieve_order: int | None
    location: Location | None
    crane: int | None


@dataclass(frozen=True, slots=True)
class OrderDetails:
    order_id: str
    type: str
    arrival_s: float | None
    start_s: float | None
    completion_s: float | None
    location: Location | None
    end: str | None


@dataclass(frozen=True, slots=True)
class CellDetails:
    location: Location
    state: str
    load: LoadUnit | None


@dataclass(frozen=True, slots=True)
class HandlingStep:
    """A crane picking or setting. With no location, it does so at an aisle end."""

    kind: str
    location: Location | None
    start_s: float
    end_s: float


@dataclass(frozen=True, slots=True)
class CraneState:
    aisle: int
    activity: str
    order: int | None
    carrying: str | None
    position: tuple[float, float]
    movement_target: tuple[float, float] | None
    handling: HandlingStep | None = None


@dataclass(frozen=True, slots=True)
class Backlog:
    total: int
    per_aisle: dict[int, int]
    waiting_for_cell: int


@dataclass(frozen=True, slots=True)
class RunState:
    time_s: float
    in_measurement_window: bool
    backlog: Backlog
    occupied_cells: int
    occupancy: float
    completed: int
    arrived: int
    unfulfillable: int
    cranes: dict[int, CraneState]


@dataclass(frozen=True, slots=True)
class CellChanges:
    all: bool
    cells: list[Location]


@runtime_checkable
class StateSource(Protocol):
    """Delivers run state. It has no operation that writes anything."""

    @property
    def range_is_final(self) -> bool: ...

    @property
    def can_move_backward(self) -> bool: ...

    def describe(self) -> WarehouseDescription: ...

    def time_range(self) -> tuple[float, float]: ...

    def state_at(self, time_s: float) -> RunState: ...

    def take_changes(self) -> CellChanges: ...

    def stored_load_units(self) -> list[LoadUnit]: ...

    def cell(self, location: Location) -> CellDetails: ...

    def load(self, key: str) -> LoadUnit | None: ...

    def order(self, index: int) -> OrderDetails: ...
