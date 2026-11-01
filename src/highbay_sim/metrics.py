"""Metric calculation and written definitions, as in contracts/results.md.

Metrics are calculated only from a run's events and initial state, so they use the same stream
that any other consumer of a run receives.
"""

import math
from dataclasses import dataclass
from itertools import groupby

from highbay_sim.engine import RunRecord
from highbay_sim.events import SimulationEvent

SECONDS_PER_HOUR = 3600.0

DEFINITIONS: dict[str, dict[str, str]] = {
    "throughput_per_hour": {
        "unit": "orders/hour",
        "definition": (
            "Orders with a completion time in the measurement window, divided by the window "
            "length in hours. An order is completed when its load unit has been set down at its "
            "destination cell or transfer point."
        ),
    },
    "order_cycle_time_s": {
        "unit": "seconds",
        "definition": (
            "Completion time minus arrival time, for orders completed in the window. The median "
            "is the middle value or the average of the two middle values, and the 95th percentile "
            "uses the nearest-rank method."
        ),
    },
    "order_waiting_time_s": {
        "unit": "seconds",
        "definition": (
            "Start time minus arrival time, for orders started in the window, where an order "
            "starts when a crane starts working on it. Statistics are calculated as for the "
            "order cycle time."
        ),
    },
    "crane_utilization": {
        "unit": "share of window (0 to 1)",
        "definition": (
            "Time in each activity within the window, divided by the window length. Activities "
            "crossing a window boundary count only their share inside it."
        ),
    },
    "backlog_orders": {
        "unit": "orders",
        "definition": (
            "Orders that have arrived but have not started and are not unfulfillable. An order "
            "that starts at the moment it arrives is not counted."
        ),
    },
    "storage_occupancy": {
        "unit": "share of cells (0 to 1)",
        "definition": "Cells physically holding a load unit, divided by all cells.",
    },
    "order_outcomes": {
        "unit": "orders",
        "definition": (
            "Number of orders by final outcome over the whole run, including the warm-up. "
            "Generated counts all orders that arrived, including explicitly listed ones."
        ),
    },
}


@dataclass(frozen=True)
class TimeStatistics:
    mean: float | None
    median: float | None
    p95: float | None
    max: float | None


@dataclass(frozen=True)
class CraneUtilization:
    moving_loaded: float
    moving_empty: float
    handling: float
    idle: float


@dataclass(frozen=True)
class Metrics:
    window_start_s: float
    window_end_s: float
    throughput_total: float
    throughput_storage: float
    throughput_retrieval: float
    order_cycle_time: TimeStatistics
    order_waiting_time: TimeStatistics
    crane_utilization: dict[int, CraneUtilization]
    backlog_at_window_end: int
    backlog_max_in_window: int
    occupancy_at_window_start: float
    occupancy_at_window_end: float
    orders_generated: int
    orders_completed: int
    orders_unfinished: int
    orders_unfulfillable: int


def calculate_metrics(record: RunRecord, warmup_s: float) -> Metrics:
    """Calculate all metrics from a run's events and initial state, without re-simulating."""
    if not 0.0 <= warmup_s < record.duration_s:
        raise ValueError("the warm-up must be shorter than the run")
    start_s, end_s = warmup_s, record.duration_s
    window_hours = (end_s - start_s) / SECONDS_PER_HOUR

    arrivals: dict[str, float] = {}
    cycle_times: list[float] = []
    waiting_times: list[float] = []
    completed = {"storage": 0, "retrieval": 0}
    orders_completed = 0
    orders_unfulfillable = 0
    for event in record.events:
        inside = start_s <= event.time_s <= end_s
        if event.kind == "order_arrived":
            arrivals[event.order_id] = event.time_s
        elif event.kind == "order_unfulfillable":
            orders_unfulfillable += 1
        elif event.kind == "order_started" and inside:
            waiting_times.append(event.time_s - arrivals[event.order_id])
        elif event.kind == "order_completed":
            orders_completed += 1
            if inside:
                cycle_times.append(event.time_s - arrivals[event.order_id])
                completed[event.order_type] += 1

    backlog_at_end, backlog_max = _backlog(record.events, start_s)
    occupied_start, occupied_end = _occupied_cells(record, start_s)
    return Metrics(
        window_start_s=start_s,
        window_end_s=end_s,
        throughput_total=(completed["storage"] + completed["retrieval"]) / window_hours,
        throughput_storage=completed["storage"] / window_hours,
        throughput_retrieval=completed["retrieval"] / window_hours,
        order_cycle_time=_statistics(cycle_times),
        order_waiting_time=_statistics(waiting_times),
        crane_utilization=_utilization(record, start_s, end_s),
        backlog_at_window_end=backlog_at_end,
        backlog_max_in_window=backlog_max,
        occupancy_at_window_start=occupied_start / record.cell_count,
        occupancy_at_window_end=occupied_end / record.cell_count,
        orders_generated=len(arrivals),
        orders_completed=orders_completed,
        orders_unfinished=len(arrivals) - orders_completed - orders_unfulfillable,
        orders_unfulfillable=orders_unfulfillable,
    )


def _statistics(values: list[float]) -> TimeStatistics:
    if not values:
        return TimeStatistics(None, None, None, None)
    ordered = sorted(values)
    count = len(ordered)
    middle = count // 2
    median = ordered[middle] if count % 2 else (ordered[middle - 1] + ordered[middle]) / 2.0
    nearest_rank = (95 * count + 99) // 100
    return TimeStatistics(
        mean=math.fsum(ordered) / count,
        median=median,
        p95=ordered[nearest_rank - 1],
        max=ordered[-1],
    )


def _backlog(events: tuple[SimulationEvent, ...], start_s: float) -> tuple[int, int]:
    """Return the backlog at the end and its maximum in the window.

    Events with equal times are applied together, so an order that starts as it arrives never
    counts as waiting.
    """
    backlog = 0
    maximum = 0
    for time_s, group in groupby(events, key=lambda event: event.time_s):
        for event in group:
            if event.kind == "order_arrived":
                backlog += 1
            elif event.kind in ("order_started", "order_unfulfillable"):
                backlog -= 1
        maximum = backlog if time_s <= start_s else max(maximum, backlog)
    return backlog, maximum


def _occupied_cells(record: RunRecord, start_s: float) -> tuple[int, int]:
    occupied = record.initial_occupied
    at_start = occupied
    for event in record.events:
        if event.location is not None:
            if event.kind == "load_set":
                occupied += 1
            elif event.kind == "load_picked":
                occupied -= 1
        if event.time_s <= start_s:
            at_start = occupied
    return at_start, occupied


def _utilization(record: RunRecord, start_s: float, end_s: float) -> dict[int, CraneUtilization]:
    busy = {
        crane: {"moving_loaded": 0.0, "moving_empty": 0.0, "handling": 0.0}
        for crane in range(1, record.crane_count + 1)
    }
    for event in record.events:
        if event.kind != "activity_started":
            continue
        assert event.crane is not None and event.activity is not None and event.end_s is not None
        inside = min(event.end_s, end_s) - max(event.time_s, start_s)
        if inside > 0.0:
            busy[event.crane][event.activity] += inside

    window = end_s - start_s
    return {
        crane: CraneUtilization(
            moving_loaded=times["moving_loaded"] / window,
            moving_empty=times["moving_empty"] / window,
            handling=times["handling"] / window,
            idle=1.0 - math.fsum(times.values()) / window,
        )
        for crane, times in busy.items()
    }
