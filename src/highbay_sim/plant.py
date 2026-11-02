"""The plant model: cranes, cells, and inbound points, advanced one fixed cycle at a time.

The plant changes only through time and through the commands in the signal interface. It keeps its
state privately and writes every status signal in each cycle, so writing to a status signal has no
effect. This module uses no files, network, display, or system clock.
"""

import math
from collections.abc import Mapping
from typing import Literal, Protocol

from highbay_sim.allocation import end_position
from highbay_sim.config import End, WarehouseDefinition
from highbay_sim.events import Location, Position
from highbay_sim.kinematics import axis_position, axis_travel_time
from highbay_sim.signals import CraneSignals, Fault, FaultCode

POSITION_TOLERANCE_M = 0.001
ROUNDING_MARGIN = 1e-9
Place = Location | End


class PlantObserver(Protocol):
    """How the simulation learns what the plant does. A controller never gets these calls."""

    def movement_started(
        self,
        aisle: int,
        time_s: float,
        start: Position,
        target: Position,
        end_s: float,
        loaded: bool,
    ) -> None: ...

    def handling_started(self, aisle: int, time_s: float, end_s: float) -> None: ...

    def pick_finished(self, aisle: int, time_s: float, place: Place) -> None: ...

    def set_finished(self, aisle: int, time_s: float, place: Place) -> None: ...


class _Axis:
    __slots__ = ("acceleration", "end_cycle", "position", "speed", "start", "start_cycle", "target")

    def __init__(self, position: float, speed: float, acceleration: float) -> None:
        self.position = position
        self.speed = speed
        self.acceleration = acceleration
        self.start = self.target = position
        self.start_cycle = self.end_cycle = 0

    @property
    def is_moving(self) -> bool:
        return self.position != self.target


class _Crane:
    __slots__ = (
        "aisle",
        "fault",
        "handling",
        "handling_end_cycle",
        "handling_place",
        "horizontal",
        "last_fault_reset",
        "last_horizontal_start",
        "last_pick_start",
        "last_set_start",
        "last_vertical_start",
        "load",
        "signals",
        "vertical",
    )

    def __init__(
        self, aisle: int, signals: CraneSignals, horizontal: _Axis, vertical: _Axis
    ) -> None:
        self.aisle = aisle
        self.signals = signals
        self.horizontal = horizontal
        self.vertical = vertical
        self.load: str | None = None
        self.handling: Literal["pick", "set"] | None = None
        self.handling_end_cycle = 0
        self.handling_place: Place | None = None
        self.fault = FaultCode.NONE
        self.last_fault_reset = False
        self.last_horizontal_start = False
        self.last_vertical_start = False
        self.last_pick_start = False
        self.last_set_start = False


class Plant:
    def __init__(
        self,
        warehouse: WarehouseDefinition,
        cycle_ms: int,
        signals: Mapping[int, CraneSignals],
        observer: PlantObserver,
    ) -> None:
        self._warehouse = warehouse
        self._layout = warehouse.layout
        self._cycle_ms = cycle_ms
        self._cycle_s = cycle_ms / 1000
        self._observer = observer
        self._cells: dict[Location, str] = {
            (
                entry.location.aisle,
                entry.location.rack,
                entry.location.bay,
                entry.location.level,
            ): entry.article
            for entry in warehouse.initial_stock
        }
        self._offered: dict[tuple[int, End], str] = {}
        self.faults: list[Fault] = []
        self._cranes = [self._new_crane(aisle, signals[aisle]) for aisle in sorted(signals)]
        for crane in self._cranes:
            self._write_status(crane)

    def _new_crane(self, aisle: int, signals: CraneSignals) -> _Crane:
        parameters = self._warehouse.crane
        start = end_position(self._layout, self._warehouse.ends_with_role(aisle, "inbound")[0])
        return _Crane(
            aisle,
            signals,
            _Axis(
                start[0], parameters.horizontal.speed_m_s, parameters.horizontal.acceleration_m_s2
            ),
            _Axis(start[1], parameters.vertical.speed_m_s, parameters.vertical.acceleration_m_s2),
        )

    def cell_contents(self) -> dict[Location, str]:
        """Return the article of the load unit in each occupied cell."""
        return dict(self._cells)

    def load_on_crane(self, aisle: int) -> str | None:
        return self._cranes[aisle - 1].load

    def offer_load(self, aisle: int, end: End, article: str) -> None:
        """Make a load unit available at an aisle's inbound point."""
        self._offered[(aisle, end)] = article

    def advance(self, cycle: int) -> None:
        """Apply commands at the start of a cycle, then move on to the start of the next one."""
        for crane in self._cranes:
            self._apply_commands(crane, cycle)
        next_cycle = cycle + 1
        for crane in self._cranes:
            self._progress(crane, next_cycle)
            self._write_status(crane)

    def _apply_commands(self, crane: _Crane, cycle: int) -> None:
        signals = crane.signals
        horizontal_edge = signals.horizontal_start and not crane.last_horizontal_start
        vertical_edge = signals.vertical_start and not crane.last_vertical_start
        pick_edge = signals.pick_start and not crane.last_pick_start
        set_edge = signals.set_start and not crane.last_set_start
        crane.last_horizontal_start = signals.horizontal_start
        crane.last_vertical_start = signals.vertical_start
        crane.last_pick_start = signals.pick_start
        crane.last_set_start = signals.set_start
        if signals.fault_reset and not crane.last_fault_reset:
            crane.fault = FaultCode.NONE
        crane.last_fault_reset = signals.fault_reset

        if crane.fault is not FaultCode.NONE:
            return
        if pick_edge and set_edge:
            self._refuse(crane, cycle, FaultCode.CONFLICTING_COMMANDS, "Pick and set both started.")
            return
        if horizontal_edge or vertical_edge:
            self._start_movement(crane, horizontal_edge, vertical_edge, cycle)
        if pick_edge:
            self._start_handling(crane, "pick", cycle)
        elif set_edge:
            self._start_handling(crane, "set", cycle)

    def _refuse(self, crane: _Crane, cycle: int, code: FaultCode, description: str) -> None:
        crane.fault = code
        self.faults.append(Fault(cycle, self._time(cycle), crane.aisle, code, description))

    def _is_busy(self, crane: _Crane) -> bool:
        return crane.horizontal.is_moving or crane.vertical.is_moving or crane.handling is not None

    def _start_movement(
        self, crane: _Crane, horizontal_edge: bool, vertical_edge: bool, cycle: int
    ) -> None:
        signals = crane.signals
        start = (crane.horizontal.position, crane.vertical.position)
        if self._is_busy(crane):
            self._refuse(crane, cycle, FaultCode.CRANE_BUSY, f"A start arrived at {start} m.")
            return
        layout = self._layout
        horizontal_range = layout.bays_per_rack * layout.cell.length_m
        vertical_range = (layout.levels_per_rack - 1) * layout.cell.height_m
        if (horizontal_edge and not 0.0 <= signals.horizontal_target_m <= horizontal_range) or (
            vertical_edge and not 0.0 <= signals.vertical_target_m <= vertical_range
        ):
            target = (signals.horizontal_target_m, signals.vertical_target_m)
            self._refuse(
                crane, cycle, FaultCode.TARGET_OUT_OF_RANGE, f"The target {target} m is outside."
            )
            return
        if horizontal_edge:
            self._start_axis(crane.horizontal, signals.horizontal_target_m, cycle)
        if vertical_edge:
            self._start_axis(crane.vertical, signals.vertical_target_m, cycle)
        end_cycle = max(crane.horizontal.end_cycle, crane.vertical.end_cycle)
        if crane.horizontal.is_moving or crane.vertical.is_moving:
            self._observer.movement_started(
                crane.aisle,
                self._time(cycle),
                start,
                (crane.horizontal.target, crane.vertical.target),
                self._time(end_cycle),
                crane.load is not None,
            )

    def _start_axis(self, axis: _Axis, target: float, cycle: int) -> None:
        axis.start = axis.position
        axis.target = target
        axis.start_cycle = cycle
        travel_s = axis_travel_time(target - axis.position, axis.speed, axis.acceleration)
        axis.end_cycle = cycle + self._cycles(travel_s)

    def _cycles(self, duration_s: float) -> int:
        """Return how many whole cycles cover a duration."""
        return math.ceil(duration_s / self._cycle_s - ROUNDING_MARGIN)

    def _time(self, cycle: int) -> float:
        return cycle * self._cycle_ms / 1000

    def _start_handling(self, crane: _Crane, kind: Literal["pick", "set"], cycle: int) -> None:
        position = (crane.horizontal.position, crane.vertical.position)
        if self._is_busy(crane):
            self._refuse(crane, cycle, FaultCode.CRANE_BUSY, f"A {kind} arrived at {position} m.")
            return
        place = self._place(crane)
        code = FaultCode.NO_PLACE if place is None else self._handling_fault(crane, kind, place)
        if code is not FaultCode.NONE:
            self._refuse(
                crane, cycle, code, f"A {kind} at {position} m, side {crane.signals.side}."
            )
            return
        parameters = self._warehouse.crane
        duration_s = parameters.pick_time_s if kind == "pick" else parameters.set_time_s
        crane.handling = kind
        crane.handling_place = place
        crane.handling_end_cycle = cycle + max(self._cycles(duration_s), 1)
        self._observer.handling_started(
            crane.aisle, self._time(cycle), self._time(crane.handling_end_cycle)
        )

    def _handling_fault(
        self, crane: _Crane, kind: Literal["pick", "set"], place: Place
    ) -> FaultCode:
        if isinstance(place, tuple) and not 1 <= place[1] <= self._layout.racks_per_aisle:
            return FaultCode.INVALID_SIDE
        if kind == "pick":
            if crane.load is not None:
                return FaultCode.CRANE_ALREADY_LOADED
            available = (
                place in self._cells
                if isinstance(place, tuple)
                else (crane.aisle, place) in self._offered
            )
            return FaultCode.NONE if available else FaultCode.NOTHING_TO_PICK
        if crane.load is None:
            return FaultCode.CRANE_EMPTY
        if isinstance(place, tuple):
            return FaultCode.PLACE_OCCUPIED if place in self._cells else FaultCode.NONE
        if place in self._warehouse.ends_with_role(crane.aisle, "outbound"):
            return FaultCode.NONE
        return FaultCode.SET_NOT_ALLOWED

    def _place(self, crane: _Crane) -> Place | None:
        """Return the cell or aisle end at the crane's position, for its current side."""
        horizontal = crane.horizontal.position
        vertical = crane.vertical.position
        layout = self._layout
        if abs(vertical) <= POSITION_TOLERANCE_M:
            for end in ("left", "right"):
                if abs(horizontal - end_position(layout, end)[0]) <= POSITION_TOLERANCE_M:
                    return end
        bay = round(horizontal / layout.cell.length_m + 0.5)
        level = round(vertical / layout.cell.height_m + 1)
        is_bay = abs((bay - 0.5) * layout.cell.length_m - horizontal) <= POSITION_TOLERANCE_M
        is_level = abs((level - 1) * layout.cell.height_m - vertical) <= POSITION_TOLERANCE_M
        in_range = 1 <= bay <= layout.bays_per_rack and 1 <= level <= layout.levels_per_rack
        if is_bay and is_level and in_range:
            return (crane.aisle, crane.signals.side, bay, level)
        return None

    def _progress(self, crane: _Crane, next_cycle: int) -> None:
        self._progress_axis(crane.horizontal, next_cycle)
        self._progress_axis(crane.vertical, next_cycle)
        if crane.handling is not None and next_cycle >= crane.handling_end_cycle:
            self._finish_handling(crane, next_cycle)

    def _progress_axis(self, axis: _Axis, next_cycle: int) -> None:
        if not axis.is_moving:
            return
        if next_cycle >= axis.end_cycle:
            axis.position = axis.target
        else:
            axis.position = axis_position(
                axis.start,
                axis.target,
                axis.speed,
                axis.acceleration,
                (next_cycle - axis.start_cycle) * self._cycle_s,
            )

    def _finish_handling(self, crane: _Crane, next_cycle: int) -> None:
        kind = crane.handling
        place = crane.handling_place
        crane.handling = None
        crane.handling_place = None
        time_s = self._time(next_cycle)
        if kind == "pick":
            if isinstance(place, tuple):
                crane.load = self._cells.pop(place)
            else:
                assert place is not None
                crane.load = self._offered.pop((crane.aisle, place))
            assert place is not None
            self._observer.pick_finished(crane.aisle, time_s, place)
            return
        assert crane.load is not None and place is not None
        if isinstance(place, tuple):
            self._cells[place] = crane.load
        crane.load = None
        self._observer.set_finished(crane.aisle, time_s, place)

    def _write_status(self, crane: _Crane) -> None:
        signals = crane.signals
        signals.horizontal_actual_m = crane.horizontal.position
        signals.vertical_actual_m = crane.vertical.position
        signals.horizontal_in_position = not crane.horizontal.is_moving
        signals.vertical_in_position = not crane.vertical.is_moving
        signals.handling_active = crane.handling is not None
        signals.load_present = crane.load is not None
        signals.fault_code = crane.fault
