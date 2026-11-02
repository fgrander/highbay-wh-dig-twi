"""The cycle loop of a time-stepped run, which produces the same record as an event-based run.

This module uses no files, network, display, or system clock. Same arguments and software version
give the same record. Each cycle runs order handling, then the controller, then the plant.
"""

import math
from collections.abc import Callable, Iterator
from dataclasses import dataclass

from highbay_sim.config import WarehouseDefinition
from highbay_sim.controller import BuiltInController, Controller
from highbay_sim.engine import RunRecord
from highbay_sim.events import Activity, EventKind, Location, Position, SimulationEvent
from highbay_sim.order_handling import OrderHandling, OrderRecord
from highbay_sim.orders import OrderRequest, OrderSource
from highbay_sim.plant import Place, Plant
from highbay_sim.signals import CraneSignals, Fault

DEFAULT_CYCLE_MS = 50
MIN_CYCLE_MS = 1
MAX_CYCLE_MS = 1000
ROUNDING_MARGIN = 1e-9


class ControllerError(Exception):
    pass


@dataclass(frozen=True)
class SteppedRun:
    record: RunRecord
    faults: tuple[Fault, ...]


@dataclass
class _Job:
    job_id: int
    order: OrderRecord
    is_picked: bool = False
    is_set_down: bool = False


def simulate_stepped(
    warehouse: WarehouseDefinition,
    order_source: OrderSource,
    seed: int,
    duration_s: float,
    cycle_ms: int = DEFAULT_CYCLE_MS,
    controller: Controller | None = None,
    on_cycle: Callable[[int, float], None] | None = None,
    signals: dict[int, CraneSignals] | None = None,
) -> SteppedRun:
    """Run one simulation in fixed cycles. Same arguments and version give the same record.

    on_cycle is called once per cycle, after the controller and before the plant advances, when
    all signals show their values at that cycle's start.
    """
    return _Run(
        warehouse,
        order_source,
        seed,
        duration_s,
        cycle_ms,
        controller,
        on_cycle,
        new_signals(warehouse) if signals is None else signals,
    ).execute()


def new_signals(warehouse: WarehouseDefinition) -> dict[int, CraneSignals]:
    return {aisle: CraneSignals() for aisle in range(1, warehouse.layout.aisle_count + 1)}


class _Run:
    def __init__(
        self,
        warehouse: WarehouseDefinition,
        order_source: OrderSource,
        seed: int,
        duration_s: float,
        cycle_ms: int,
        controller: Controller | None,
        on_cycle: Callable[[int, float], None] | None,
        signals: dict[int, CraneSignals],
    ) -> None:
        self._layout = warehouse.layout
        self._duration_s = duration_s
        self._cycle_ms = cycle_ms
        self._on_cycle = on_cycle
        self._controller = BuiltInController() if controller is None else controller
        self._requests: Iterator[OrderRequest] = iter(order_source.orders(duration_s))
        self._next_request = next(self._requests, None)
        self.signals = signals
        self._handling = OrderHandling(warehouse, seed, self._emit, lambda aisle: None)
        self._plant = Plant(warehouse, cycle_ms, self.signals, self)
        self._jobs: dict[int, _Job] = {}
        self._job_numbers = dict.fromkeys(self.signals, 0)
        self._now = 0.0
        self._events: list[SimulationEvent] = []

    def execute(self) -> SteppedRun:
        last_cycle = math.floor(self._duration_s * 1000 / self._cycle_ms + ROUNDING_MARGIN)
        for cycle in range(last_cycle + 1):
            self._now = cycle * self._cycle_ms / 1000
            self._handle_orders()
            try:
                self._controller.scan(self.signals)
            except Exception as error:
                raise ControllerError(f"the controller failed in cycle {cycle}: {error}") from error
            if self._on_cycle is not None:
                self._on_cycle(cycle, cycle * self._cycle_ms / 1000)
            if cycle < last_cycle:
                self._plant.advance(cycle)
        self._process_last_arrivals()
        self._handling.set_final_reasons()
        return SteppedRun(
            RunRecord(
                events=tuple(self._events),
                orders=tuple(self._handling.orders),
                duration_s=self._duration_s,
                cell_count=self._handling.allocation.cell_count,
                crane_count=len(self.signals),
                initial_occupied=self._handling.allocation.initial_occupied,
            ),
            tuple(self._plant.faults),
        )

    def _handle_orders(self) -> None:
        for aisle, job in list(self._jobs.items()):
            if self.signals[aisle].job_done_id == job.job_id and job.is_set_down:
                self._complete(aisle, job)
        while self._next_request is not None and self._next_request.arrival_s <= self._now:
            self._arrive()
        for aisle in self.signals:
            if aisle not in self._jobs:
                self._start_next_order(aisle)

    def _arrive(self) -> None:
        assert self._next_request is not None
        self._handling.arrive(self._next_request)
        self._next_request = next(self._requests, None)

    def _process_last_arrivals(self) -> None:
        while self._next_request is not None:
            self._now = self._next_request.arrival_s
            self._arrive()

    def _complete(self, aisle: int, job: _Job) -> None:
        job.order.outcome = "completed"
        job.order.completion_s = self._now
        self._emit("order_completed", job.order, job.order.location)
        del self._jobs[aisle]

    def _start_next_order(self, aisle: int) -> None:
        order = self._handling.next_order(aisle)
        if order is None:
            return
        assert order.location is not None
        crane = self.signals[aisle]
        order.start_s = self._now
        self._emit("order_started", order, order.location)
        position = (crane.horizontal_actual_m, crane.vertical_actual_m)
        source, destination = self._handling.plan_transport(order, position)
        rack = order.location[1]
        if order.order_type == "storage":
            assert order.transfer_point is not None
            self._plant.offer_load(aisle, order.transfer_point, order.article)
            source_side, destination_side = 0, rack
        else:
            source_side, destination_side = rack, 0
        self._job_numbers[aisle] += 1
        job_id = self._job_numbers[aisle]
        self._jobs[aisle] = _Job(job_id, order)
        crane.source_horizontal_m, crane.source_vertical_m = source
        crane.source_side = source_side
        crane.destination_horizontal_m, crane.destination_vertical_m = destination
        crane.destination_side = destination_side
        crane.job_id = job_id

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
        self._events.append(
            SimulationEvent(
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
        )

    def movement_started(
        self,
        aisle: int,
        time_s: float,
        start: Position,
        target: Position,
        end_s: float,
        loaded: bool,
    ) -> None:
        job = self._jobs.get(aisle)
        if job is not None:
            self._now = time_s
            activity: Activity = "moving_loaded" if loaded else "moving_empty"
            self._emit(
                "activity_started", job.order, job.order.location, activity, end_s, start, target
            )

    def handling_started(self, aisle: int, time_s: float, end_s: float) -> None:
        job = self._jobs.get(aisle)
        if job is not None:
            self._now = time_s
            self._emit("activity_started", job.order, job.order.location, "handling", end_s)

    def pick_finished(self, aisle: int, time_s: float, place: Place) -> None:
        job = self._jobs.get(aisle)
        if job is None or job.is_picked or place != _pick_place(job.order):
            return
        self._now = time_s
        self._handling.finish_pick(job.order)
        job.is_picked = True

    def set_finished(self, aisle: int, time_s: float, place: Place) -> None:
        job = self._jobs.get(aisle)
        if job is None or not job.is_picked or place != _set_place(job.order):
            return
        self._now = time_s
        self._handling.finish_set(job.order)
        job.is_set_down = True


def _pick_place(order: OrderRecord) -> Place | None:
    return order.transfer_point if order.order_type == "storage" else order.location


def _set_place(order: OrderRecord) -> Place | None:
    return order.location if order.order_type == "storage" else order.transfer_point
