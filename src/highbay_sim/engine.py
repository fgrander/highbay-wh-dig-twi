"""Discrete-event loop and crane behavior.

This module uses no files, network, display, or system clock. Same arguments and software version
give the same events and record. Events with equal times run in the order they were scheduled.
"""

import heapq
from collections import deque
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Literal

from highbay_sim.allocation import Allocation, cell_position, end_position
from highbay_sim.config import End, Role, WarehouseDefinition
from highbay_sim.events import Activity, EventKind, Location, OrderType, SimulationEvent
from highbay_sim.kinematics import movement_time
from highbay_sim.orders import OrderRequest, OrderSource

Outcome = Literal["completed", "unfinished", "unfulfillable"]
Position = tuple[float, float]


@dataclass
class OrderRecord:
    order_id: str
    order_type: OrderType
    article: str
    arrival_s: float
    start_s: float | None = None
    completion_s: float | None = None
    crane: int | None = None
    location: Location | None = None
    transfer_point: End | None = None
    outcome: Outcome = "unfinished"
    reason: str = ""


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
    queue: deque[OrderRecord] = field(default_factory=deque)
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
        self._layout = warehouse.layout
        self._duration_s = duration_s
        self._on_event = on_event
        self._requests: Iterator[OrderRequest] = iter(order_source.orders(duration_s))
        self._allocation = Allocation(warehouse, seed)
        self._cranes = {
            aisle: _Crane(aisle, self._end_position(warehouse.ends_with_role(aisle, "inbound")[0]))
            for aisle in range(1, self._layout.aisle_count + 1)
        }
        self._now = 0.0
        self._schedule_sequence = 0
        self._schedule: list[tuple[float, int, OrderRequest | _Crane]] = []
        self._events: list[SimulationEvent] = []
        self._orders: list[OrderRecord] = []
        self._waiting_for_cell: deque[OrderRecord] = deque()

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
                self._arrive(item)
                self._schedule_next_arrival()
        for order in self._orders:
            self._set_final_reason(order)
        return RunRecord(
            events=tuple(self._events),
            orders=tuple(self._orders),
            duration_s=self._duration_s,
            cell_count=self._allocation.cell_count,
            crane_count=len(self._cranes),
            initial_occupied=self._allocation.initial_occupied,
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

    def _arrive(self, request: OrderRequest) -> None:
        order = OrderRecord(
            f"O{len(self._orders) + 1:06d}",
            request.order_type,
            request.article,
            request.arrival_s,
        )
        self._orders.append(order)
        self._emit("order_arrived", order)
        if order.order_type == "storage":
            location = self._allocation.reserve_for_storage()
            if location is None:
                self._waiting_for_cell.append(order)
                self._emit("order_waiting_for_cell", order)
            else:
                self._enqueue(order, location)
            return
        location = self._allocation.reserve_for_retrieval(order.article)
        if location is None:
            order.outcome = "unfulfillable"
            order.reason = "no_stock"
            self._emit("order_unfulfillable", order)
        else:
            self._enqueue(order, location)

    def _enqueue(self, order: OrderRecord, location: Location) -> None:
        order.location = location
        order.crane = location[0]
        self._emit("order_queued", order, location)
        crane = self._cranes[location[0]]
        crane.queue.append(order)
        self._start_next_order(crane)

    def _start_next_order(self, crane: _Crane) -> None:
        if crane.order is not None or not crane.queue:
            return
        order = crane.queue.popleft()
        crane.order = order
        order.start_s = self._now
        self._emit("order_started", order, order.location)
        crane.steps = deque(self._plan_cycle(crane, order))
        self._begin_step(crane)

    def _plan_cycle(self, crane: _Crane, order: OrderRecord) -> list[_Step]:
        assert order.location is not None
        cell = cell_position(self._layout, order.location)
        parameters = self._warehouse.crane
        if order.order_type == "storage":
            end = self._best_end(
                crane.aisle,
                "inbound",
                lambda point: self._travel(crane.position, point) + self._travel(point, cell),
            )
            first_position, second_position = self._end_position(end), cell
        else:
            end = self._best_end(crane.aisle, "outbound", lambda point: self._travel(cell, point))
            first_position, second_position = cell, self._end_position(end)
        order.transfer_point = end
        return [
            _Step("moving_empty", self._travel(crane.position, first_position), first_position),
            _Step("handling", parameters.pick_time_s, finishes="pick"),
            _Step("moving_loaded", self._travel(first_position, second_position), second_position),
            _Step("handling", parameters.set_time_s, finishes="set"),
        ]

    def _best_end(self, aisle: int, role: Role, cost: Callable[[Position], float]) -> End:
        """Return the end with the lowest cost; the left end wins a tie, as it comes first."""
        return min(
            self._warehouse.ends_with_role(aisle, role),
            key=lambda end: cost(self._end_position(end)),
        )

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
            self._finish_pick(order)
        elif step.finishes == "set":
            self._finish_set(order)
        if crane.steps:
            self._begin_step(crane)
            return
        order.outcome = "completed"
        order.completion_s = self._now
        self._emit("order_completed", order, order.location)
        crane.order = None
        self._start_next_order(crane)

    def _finish_pick(self, order: OrderRecord) -> None:
        if order.order_type == "storage":
            self._emit("load_picked", order)
            return
        assert order.location is not None
        self._emit("load_picked", order, order.location)
        self._allocation.release(order.location)
        self._assign_waiting_orders()

    def _finish_set(self, order: OrderRecord) -> None:
        if order.order_type == "retrieval":
            self._emit("load_set", order)
            return
        assert order.location is not None
        self._allocation.store(order.location, order.article)
        self._emit("load_set", order, order.location)

    def _assign_waiting_orders(self) -> None:
        while self._waiting_for_cell:
            location = self._allocation.reserve_for_storage()
            if location is None:
                return
            self._enqueue(self._waiting_for_cell.popleft(), location)

    def _set_final_reason(self, order: OrderRecord) -> None:
        if order.outcome == "unfinished":
            order.reason = "no_free_cell" if order.location is None else "run_ended"

    def _end_position(self, end: End) -> Position:
        return end_position(self._layout, end)

    def _travel(self, start: Position, target: Position) -> float:
        crane = self._warehouse.crane
        return movement_time(
            target[0] - start[0],
            target[1] - start[1],
            crane.horizontal.speed_m_s,
            crane.horizontal.acceleration_m_s2,
            crane.vertical.speed_m_s,
            crane.vertical.acceleration_m_s2,
        )
