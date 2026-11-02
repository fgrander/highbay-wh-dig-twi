"""Discrete-event loop and crane behavior.

This module uses no files, network, display, or system clock. Same arguments and software version
give the same events and record. Events with equal times run in the order they were scheduled.
"""

import heapq
from collections import deque
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Literal

from highbay_sim.config import WarehouseDefinition
from highbay_sim.events import Activity, EventKind, Location, Position, SimulationEvent
from highbay_sim.order_handling import OrderHandling, OrderRecord
from highbay_sim.orders import OrderRequest, OrderSource

__all__ = ["OrderRecord", "RunRecord", "simulate"]


@dataclass(frozen=True)
class RunRecord:
    events: tuple[SimulationEvent, ...]
    orders: tuple[OrderRecord, ...]
    duration_s: float
    cell_count: int
    crane_count: int
    initial_occupied: int


@dataclass(frozen=True)
class _Step:
    activity: Activity
    duration_s: float
    position: Position | None = None
    """Where the crane is once the step ends; None if it does not move."""
    finishes: Literal["pick", "set"] | None = None


@dataclass
class _Crane:
    aisle: int
    position: Position
    order: OrderRecord | None = None
    steps: deque[_Step] = field(default_factory=deque)


def simulate(
    warehouse: WarehouseDefinition,
    order_source: OrderSource,
    seed: int,
    duration_s: float,
    on_event: Callable[[SimulationEvent], None] | None = None,
) -> RunRecord:
    """Run one simulation. Same arguments and version give the same events and record."""
    return _Run(warehouse, order_source, seed, duration_s, on_event).execute()


class _Run:
    def __init__(
        self,
        warehouse: WarehouseDefinition,
        order_source: OrderSource,
        seed: int,
        duration_s: float,
        on_event: Callable[[SimulationEvent], None] | None,
    ) -> None:
        self._warehouse = warehouse
        self._duration_s = duration_s
        self._on_event = on_event
        self._requests: Iterator[OrderRequest] = iter(order_source.orders(duration_s))
        self._handling = OrderHandling(warehouse, seed, self._emit, self._start_next_order)
        self._cranes = {
            aisle: _Crane(aisle, self._handling.start_position(aisle))
            for aisle in range(1, warehouse.layout.aisle_count + 1)
        }
        self._now = 0.0
        self._schedule_sequence = 0
        self._schedule: list[tuple[float, int, OrderRequest | _Crane]] = []
        self._events: list[SimulationEvent] = []

    def execute(self) -> RunRecord:
        self._schedule_next_arrival()
        while self._schedule:
            time_s, _, item = heapq.heappop(self._schedule)
            if time_s > self._duration_s:
                break
            self._now = time_s
            if isinstance(item, _Crane):
                self._finish_step(item)
            else:
                self._handling.arrive(item)
                self._schedule_next_arrival()
        self._handling.set_final_reasons()
        return RunRecord(
            events=tuple(self._events),
            orders=tuple(self._handling.orders),
            duration_s=self._duration_s,
            cell_count=self._handling.allocation.cell_count,
            crane_count=len(self._cranes),
            initial_occupied=self._handling.allocation.initial_occupied,
        )

    def _at(self, time_s: float, item: OrderRequest | _Crane) -> None:
        heapq.heappush(self._schedule, (time_s, self._schedule_sequence, item))
        self._schedule_sequence += 1

    def _schedule_next_arrival(self) -> None:
        request = next(self._requests, None)
        if request is not None:
            self._at(request.arrival_s, request)

    def _emit(
        self,
        kind: EventKind,
        order: OrderRecord,
        location: Location | None = None,
        activity: Activity | None = None,
        end_s: float | None = None,
        start_position: Position | None = None,
        target_position: Position | None = None,
    ) -> None:
        event = SimulationEvent(
            self._now,
            len(self._events),
            kind,
            order.order_id,
            order.order_type,
            order.crane,
            location,
            activity,
            end_s,
            start_position,
            target_position,
        )
        self._events.append(event)
        if self._on_event is not None:
            self._on_event(event)

    def _start_next_order(self, aisle: int) -> None:
        crane = self._cranes[aisle]
        if crane.order is not None:
            return
        order = self._handling.next_order(aisle)
        if order is None:
            return
        crane.order = order
        order.start_s = self._now
        self._emit("order_started", order, order.location)
        crane.steps = deque(self._plan_cycle(crane, order))
        self._begin_step(crane)

    def _plan_cycle(self, crane: _Crane, order: OrderRecord) -> list[_Step]:
        parameters = self._warehouse.crane
        first_position, second_position = self._handling.plan_transport(order, crane.position)
        travel = self._handling.travel
        return [
            _Step("moving_empty", travel(crane.position, first_position), first_position),
            _Step("handling", parameters.pick_time_s, finishes="pick"),
            _Step("moving_loaded", travel(first_position, second_position), second_position),
            _Step("handling", parameters.set_time_s, finishes="set"),
        ]

    def _begin_step(self, crane: _Crane) -> None:
        assert crane.order is not None
        step = crane.steps[0]
        end_s = self._now + step.duration_s
        self._emit(
            "activity_started",
            crane.order,
            crane.order.location,
            step.activity,
            end_s,
            None if step.position is None else crane.position,
            step.position,
        )
        self._at(end_s, crane)

    def _finish_step(self, crane: _Crane) -> None:
        order = crane.order
        assert order is not None
        step = crane.steps.popleft()
        if step.position is not None:
            crane.position = step.position
        if step.finishes == "pick":
            self._handling.finish_pick(order)
        elif step.finishes == "set":
            self._handling.finish_set(order)
        if crane.steps:
            self._begin_step(crane)
            return
        order.outcome = "completed"
        order.completion_s = self._now
        self._emit("order_completed", order, order.location)
        crane.order = None
        self._start_next_order(crane.aisle)
