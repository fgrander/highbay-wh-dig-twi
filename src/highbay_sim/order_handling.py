"""The order rules shared by both simulation modes: who gets which cell, and in which order."""

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Protocol

from highbay_sim.allocation import Allocation, cell_position, end_position
from highbay_sim.config import End, Role, WarehouseDefinition
from highbay_sim.events import EventKind, Location, OrderType, Position
from highbay_sim.kinematics import movement_time
from highbay_sim.orders import OrderRequest

Outcome = Literal["completed", "unfinished", "unfulfillable"]


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


class Emit(Protocol):
    def __call__(
        self, kind: EventKind, order: OrderRecord, location: Location | None = None, /
    ) -> None: ...


class OrderHandling:
    def __init__(
        self,
        warehouse: WarehouseDefinition,
        seed: int,
        emit: Emit,
        on_queued: Callable[[int], None],
    ) -> None:
        self._warehouse = warehouse
        self._layout = warehouse.layout
        self._emit = emit
        self._on_queued = on_queued
        self.allocation = Allocation(warehouse, seed)
        self.orders: list[OrderRecord] = []
        self._queues: dict[int, deque[OrderRecord]] = {
            aisle: deque() for aisle in range(1, self._layout.aisle_count + 1)
        }
        self._waiting_for_cell: deque[OrderRecord] = deque()

    def start_position(self, aisle: int) -> Position:
        """Return where an aisle's crane starts: its first inbound point, left before right."""
        return end_position(self._layout, self._warehouse.ends_with_role(aisle, "inbound")[0])

    def arrive(self, request: OrderRequest) -> None:
        order = OrderRecord(
            f"O{len(self.orders) + 1:06d}",
            request.order_type,
            request.article,
            request.arrival_s,
        )
        self.orders.append(order)
        self._emit("order_arrived", order)
        if order.order_type == "storage":
            location = self.allocation.reserve_for_storage()
            if location is None:
                self._waiting_for_cell.append(order)
                self._emit("order_waiting_for_cell", order)
            else:
                self._enqueue(order, location)
            return
        location = self.allocation.reserve_for_retrieval(order.article)
        if location is None:
            order.outcome = "unfulfillable"
            order.reason = "no_stock"
            self._emit("order_unfulfillable", order)
        else:
            self._enqueue(order, location)

    def next_order(self, aisle: int) -> OrderRecord | None:
        """Return the aisle's next order, taking it out of the queue."""
        queue = self._queues[aisle]
        return queue.popleft() if queue else None

    def plan_transport(
        self, order: OrderRecord, crane_position: Position
    ) -> tuple[Position, Position]:
        """Choose an order's aisle end, and return where its load is picked and where it is set."""
        assert order.location is not None and order.crane is not None
        cell = cell_position(self._layout, order.location)
        if order.order_type == "storage":
            end = self._best_end(
                order.crane,
                "inbound",
                lambda point: self.travel(crane_position, point) + self.travel(point, cell),
            )
            order.transfer_point = end
            return end_position(self._layout, end), cell
        end = self._best_end(order.crane, "outbound", lambda point: self.travel(cell, point))
        order.transfer_point = end
        return cell, end_position(self._layout, end)

    def finish_pick(self, order: OrderRecord) -> None:
        if order.order_type == "storage":
            self._emit("load_picked", order)
            return
        assert order.location is not None
        self._emit("load_picked", order, order.location)
        self.allocation.release(order.location)
        self._assign_waiting_orders()

    def finish_set(self, order: OrderRecord) -> None:
        if order.order_type == "retrieval":
            self._emit("load_set", order)
            return
        assert order.location is not None
        self.allocation.store(order.location, order.article)
        self._emit("load_set", order, order.location)

    def set_final_reasons(self) -> None:
        for order in self.orders:
            if order.outcome == "unfinished":
                order.reason = "no_free_cell" if order.location is None else "run_ended"

    def travel(self, start: Position, target: Position) -> float:
        crane = self._warehouse.crane
        return movement_time(
            target[0] - start[0],
            target[1] - start[1],
            crane.horizontal.speed_m_s,
            crane.horizontal.acceleration_m_s2,
            crane.vertical.speed_m_s,
            crane.vertical.acceleration_m_s2,
        )

    def _enqueue(self, order: OrderRecord, location: Location) -> None:
        order.location = location
        order.crane = location[0]
        self._emit("order_queued", order, location)
        self._queues[location[0]].append(order)
        self._on_queued(location[0])

    def _best_end(self, aisle: int, role: Role, cost: Callable[[Position], float]) -> End:
        """Return the end with the lowest cost; the left end wins a tie, as it comes first."""
        return min(
            self._warehouse.ends_with_role(aisle, role),
            key=lambda end: cost(end_position(self._layout, end)),
        )

    def _assign_waiting_orders(self) -> None:
        while self._waiting_for_cell:
            location = self.allocation.reserve_for_storage()
            if location is None:
                return
            self._enqueue(self._waiting_for_cell.popleft(), location)
