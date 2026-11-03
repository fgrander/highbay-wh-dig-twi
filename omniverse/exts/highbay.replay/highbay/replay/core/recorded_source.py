"""State from a recording, by the same rules as the browser viewer's replay-state.js.

There is one path to any state: events are applied in order up to the time, continuing forward or
starting again when moving backward. The result therefore depends only on the time and the data.
"""

from bisect import bisect_right
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from .motion import movement_position
from .recording import RECORDING_FILE, load_recording
from .state_source import (
    Backlog,
    CellChanges,
    CellDetails,
    CraneState,
    HandlingStep,
    LoadUnit,
    Location,
    OrderDetails,
    RunState,
    StateSourceError,
    WarehouseDescription,
)

_TIME = 0
_KIND = 1
_ORDER = 2
_CRANE = 3
_LOCATION = 4
_ACTIVITY = 5
_END = 6
_START_POSITION = 7
_TARGET_POSITION = 8
_ORDER_ID = 0
_ORDER_TYPE = 1
_ORDER_ARTICLE = 2
_ORDER_ARRIVAL = 3
_ORDER_START = 4
_ORDER_COMPLETION = 5
_ORDER_LOCATION = 7
_ORDER_END = 8
_STEP_KINDS = {"load_picked": "pick", "load_set": "set"}
_SAME_TIME_S = 1e-9


@dataclass(slots=True)
class _Activity:
    start_s: float
    end_s: float
    activity: str
    order: int | None
    step: HandlingStep | None = None


@dataclass(slots=True)
class _Cell:
    state: str
    load: str | None


class RecordedSource:
    range_is_final = True
    can_move_backward = True

    def __init__(self, data: dict[str, Any]) -> None:
        try:
            self._prepare(data)
        except (AttributeError, IndexError, KeyError, TypeError, ValueError) as error:
            raise StateSourceError(f"the file is damaged: {error!r}") from None

    def _prepare(self, data: dict[str, Any]) -> None:
        self._data = data
        self._events: list[list[Any]] = data["events"]
        warehouse = data["warehouse"]
        layout = warehouse["layout"]
        self._crane_parameters = warehouse["crane"]
        self._start_positions = warehouse["crane_start_positions"]
        self._duration_s: float = data["run"]["duration_s"]
        self._window_start_s: float = data["run"]["window"]["start_s"]
        self._cell_count: int = (
            layout["aisle_count"]
            * layout["racks_per_aisle"]
            * layout["bays_per_rack"]
            * layout["levels_per_rack"]
        )
        self._aisles = list(range(1, layout["aisle_count"] + 1))
        self._activities: dict[int, list[_Activity]] = {aisle: [] for aisle in self._aisles}
        self._activity_starts: dict[int, list[float]] = {aisle: [] for aisle in self._aisles}
        self._movements: dict[int, list[dict[str, Any]]] = {aisle: [] for aisle in self._aisles}
        self._movement_starts: dict[int, list[float]] = {aisle: [] for aisle in self._aisles}
        self._last_handling: dict[int, int] = {}
        for row in self._events:
            if row[_KIND] == "activity_started":
                self._index_activity(row)
            elif row[_KIND] in _STEP_KINDS:
                self._index_handling_step(row)
        # Going through the whole run once finds damage now rather than during playback.
        self._reset()
        self._move_to(self._duration_s)
        for aisle in self._aisles:
            self._crane(aisle)
        self._reset()

    def _index_activity(self, row: list[Any]) -> None:
        crane = row[_CRANE]
        self._activities[crane].append(
            _Activity(row[_TIME], row[_END], row[_ACTIVITY], row[_ORDER])
        )
        self._activity_starts[crane].append(row[_TIME])
        if row[_ACTIVITY] == "handling":
            self._last_handling[crane] = len(self._activities[crane]) - 1
        if row[_START_POSITION] is not None:
            self._movements[crane].append(
                {
                    "start_s": row[_TIME],
                    "start_position": row[_START_POSITION],
                    "target_position": row[_TARGET_POSITION],
                }
            )
            self._movement_starts[crane].append(row[_TIME])

    def _index_handling_step(self, row: list[Any]) -> None:
        """Notes what a handling activity does, from the event that ends it, if there is one."""
        crane = row[_CRANE]
        index = self._last_handling.get(crane)
        if index is None:
            return
        activity = self._activities[crane][index]
        if abs(activity.end_s - row[_TIME]) > _SAME_TIME_S:
            return
        location = tuple(row[_LOCATION]) if row[_LOCATION] is not None else None
        activity.step = HandlingStep(
            _STEP_KINDS[row[_KIND]], location, activity.start_s, activity.end_s
        )

    def _reset(self) -> None:
        self._time = 0.0
        self._next_event = 0
        self._cells: dict[Location, _Cell] = {}
        self._loads: dict[str, LoadUnit] = {}
        self._carried: dict[int, str | None] = dict.fromkeys(self._aisles)
        self._waiting_orders: set[int] = set()
        self._backlog_total = 0
        self._backlog_per_aisle = dict.fromkeys(self._aisles, 0)
        self._completed = 0
        self._arrived = 0
        self._unfulfillable = 0
        self._occupied = 0
        self._changed_cells: dict[Location, None] = {}
        self._all_changed = True
        for index, (aisle, rack, bay, level, article) in enumerate(self._data["initial_stock"]):
            location = (aisle, rack, bay, level)
            key = f"i{index}"
            self._loads[key] = LoadUnit(key, article, None, None, location, None)
            self._cells[location] = _Cell("occupied", key)
            self._occupied += 1
        self._apply_events_up_to(0.0)

    def _apply_events_up_to(self, time_s: float) -> None:
        events = self._events
        while self._next_event < len(events) and events[self._next_event][_TIME] <= time_s:
            self._apply(events[self._next_event])
            self._next_event += 1

    def _apply(self, row: list[Any]) -> None:
        kind = row[_KIND]
        order = row[_ORDER]
        crane = row[_CRANE]
        location = tuple(row[_LOCATION]) if row[_LOCATION] is not None else None
        if kind == "order_arrived":
            self._arrived += 1
            self._backlog_total += 1
        elif kind == "order_waiting_for_cell":
            self._waiting_orders.add(order)
        elif kind == "order_queued":
            self._waiting_orders.discard(order)
            self._backlog_per_aisle[crane] += 1
            self._reserve_cell(order, location)  # type: ignore[arg-type]
        elif kind == "order_started":
            self._backlog_total -= 1
            self._backlog_per_aisle[crane] -= 1
        elif kind == "order_unfulfillable":
            self._backlog_total -= 1
            self._unfulfillable += 1
        elif kind == "load_picked":
            self._pick_load(order, crane, location)
        elif kind == "load_set":
            self._set_load(crane, location)
        elif kind == "order_completed":
            self._completed += 1

    def _reserve_cell(self, order: int, location: Location) -> None:
        cell = self._cells.get(location)
        if cell is not None:
            cell.state = "reserved_for_retrieval"
            self._loads[cell.load].retrieve_order = order  # type: ignore[index]
        else:
            self._cells[location] = _Cell("reserved_for_storage", None)
        self._changed_cells[location] = None

    def _pick_load(self, order: int, crane: int, location: Location | None) -> None:
        if location is None:
            key = f"o{order}"
            article = self._data["orders"][order][_ORDER_ARTICLE]
            self._loads[key] = LoadUnit(key, article, order, None, None, crane)
            self._carried[crane] = key
            return
        load = self._loads[self._cells[location].load]  # type: ignore[index]
        load.location = None
        load.crane = crane
        self._carried[crane] = load.key
        del self._cells[location]
        self._occupied -= 1
        self._changed_cells[location] = None

    def _set_load(self, crane: int, location: Location | None) -> None:
        load = self._loads[self._carried[crane]]  # type: ignore[index]
        self._carried[crane] = None
        if location is None:
            del self._loads[load.key]
            return
        load.location = location
        load.crane = None
        self._cells[location] = _Cell("occupied", load.key)
        self._occupied += 1
        self._changed_cells[location] = None

    def _move_to(self, time_s: float) -> None:
        clamped = min(max(time_s, 0.0), self._duration_s)
        if clamped < self._time:
            self._reset()
        self._apply_events_up_to(clamped)
        self._time = clamped

    def _crane(self, aisle: int) -> CraneState:
        activities = self._activities[aisle]
        index = bisect_right(self._activity_starts[aisle], self._time) - 1
        current = activities[index] if index >= 0 and self._time < activities[index].end_s else None
        movements = self._movements[aisle]
        movement_index = bisect_right(self._movement_starts[aisle], self._time) - 1
        movement = movements[movement_index] if movement_index >= 0 else None
        if movement is None:
            horizontal, vertical = self._start_positions[str(aisle)]
        else:
            horizontal, vertical = movement_position(movement, self._crane_parameters, self._time)
        target = None
        if current is not None and movement is not None and current.start_s == movement["start_s"]:
            target = (movement["target_position"][0], movement["target_position"][1])
        return CraneState(
            aisle=aisle,
            activity=current.activity if current else "idle",
            order=current.order if current else None,
            carrying=self._carried[aisle],
            position=(horizontal, vertical),
            movement_target=target,
            handling=current.step if current else None,
        )

    def describe(self) -> WarehouseDescription:
        warehouse = self._data["warehouse"]
        return WarehouseDescription(
            layout=warehouse["layout"],
            crane=warehouse["crane"],
            transfer_points=warehouse["transfer_points"],
            crane_start_positions=warehouse["crane_start_positions"],
            articles=self._data["articles"],
            run=self._data["run"],
            reported=self._data["reported"],
        )

    def time_range(self) -> tuple[float, float]:
        return (0.0, self._duration_s)

    def state_at(self, time_s: float) -> RunState:
        self._move_to(time_s)
        return RunState(
            time_s=self._time,
            in_measurement_window=self._time >= self._window_start_s,
            backlog=Backlog(
                self._backlog_total, dict(self._backlog_per_aisle), len(self._waiting_orders)
            ),
            occupied_cells=self._occupied,
            occupancy=self._occupied / self._cell_count,
            completed=self._completed,
            arrived=self._arrived,
            unfulfillable=self._unfulfillable,
            cranes={aisle: self._crane(aisle) for aisle in self._aisles},
        )

    def take_changes(self) -> CellChanges:
        changes = CellChanges(self._all_changed, list(self._changed_cells))
        self._changed_cells = {}
        self._all_changed = False
        return changes

    def stored_load_units(self) -> list[LoadUnit]:
        stored = [replace(load) for load in self._loads.values() if load.location is not None]
        return sorted(stored, key=lambda load: load.location)  # type: ignore[arg-type,return-value]

    def cell(self, location: Location) -> CellDetails:
        cell = self._cells.get(location)
        if cell is None:
            return CellDetails(location, "free", None)
        load = replace(self._loads[cell.load]) if cell.load is not None else None
        return CellDetails(location, cell.state, load)

    def load(self, key: str) -> LoadUnit | None:
        load = self._loads.get(key)
        return replace(load) if load is not None else None

    def order(self, index: int) -> OrderDetails:
        row = self._data["orders"][index]
        location = row[_ORDER_LOCATION]
        return OrderDetails(
            order_id=row[_ORDER_ID],
            type=row[_ORDER_TYPE],
            arrival_s=row[_ORDER_ARRIVAL],
            start_s=row[_ORDER_START],
            completion_s=row[_ORDER_COMPLETION],
            location=tuple(location) if location is not None else None,
            end=row[_ORDER_END],
        )


def open_recording(folder: Path | str) -> RecordedSource:
    """Opens a run folder's recording, or raises StateSourceError naming the file and problem."""
    data = load_recording(folder)
    try:
        return RecordedSource(data)
    except StateSourceError as error:
        raise StateSourceError(f"{Path(folder) / RECORDING_FILE}: {error}") from None
