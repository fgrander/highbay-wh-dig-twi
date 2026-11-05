"""The cycle loop, with the warehouse from the hand calculations.

A storage order to bay 1, level 1 from the left end: pick 10 s, move 2 m in 2·sqrt(2) s, set 10 s.
"""

import builtins
import math
import socket
import time
from collections.abc import Mapping
from typing import Any

import pytest

from conftest import minimal_warehouse_dict
from highbay_sim.config import WarehouseDefinition
from highbay_sim.controller import BuiltInController, ControllerStopped
from highbay_sim.engine import RunRecord
from highbay_sim.events import OrderType
from highbay_sim.orders import ExplicitOrders, GeneratedOrders, OrderRequest
from highbay_sim.signals import CraneSignals
from highbay_sim.stepped import ControllerError, simulate_stepped


def warehouse() -> WarehouseDefinition:
    return WarehouseDefinition.model_validate(minimal_warehouse_dict())


def run(
    orders: list[tuple[float, OrderType, str]],
    duration_s: float = 3600.0,
    cycle_ms: int = 100,
    **options: Any,
) -> RunRecord:
    source = ExplicitOrders([OrderRequest(*order) for order in orders])
    return simulate_stepped(warehouse(), source, 1, duration_s, cycle_ms, **options).record


def kinds(record: RunRecord) -> list[str]:
    return [event.kind for event in record.events]


def test_storage_order_produces_the_events_of_an_event_based_run() -> None:
    record = run([(0.0, "storage", "A")])
    assert kinds(record) == [
        "order_arrived",
        "order_queued",
        "order_started",
        "activity_started",
        "load_picked",
        "activity_started",
        "activity_started",
        "load_set",
        "order_completed",
    ]
    assert record.orders[0].outcome == "completed"


def test_times_of_a_storage_order_are_rounded_up_to_cycles() -> None:
    record = run([(0.0, "storage", "A")])
    activities = [event for event in record.events if event.kind == "activity_started"]
    # Pick 0-10 s. Move 2.83 s from 10 s rounds to 12.9 s. Set 12.9-22.9 s.
    assert [event.activity for event in activities] == ["handling", "moving_loaded", "handling"]
    assert activities[0].time_s == pytest.approx(0.0)
    assert activities[0].end_s == pytest.approx(10.0)
    assert activities[1].end_s == pytest.approx(12.9)
    assert activities[2].end_s == pytest.approx(22.9)
    # The controller reports in the cycle at 22.9 s, and order handling sees it at 23.0 s.
    assert record.orders[0].completion_s == pytest.approx(23.0)


def test_movements_carry_positions_as_in_an_event_based_run() -> None:
    record = run([(0.0, "storage", "A")])
    move = next(event for event in record.events if event.activity == "moving_loaded")
    assert move.start_position == (0.0, 0.0)
    assert move.target_position == (2.0, 0.0)
    assert move.location == (1, 1, 1, 1)


def test_event_times_never_go_backward() -> None:
    record = run([(0.0, "storage", "A"), (1.0, "storage", "A"), (2.0, "retrieval", "A")])
    times = [event.time_s for event in record.events]
    assert times == sorted(times)
    assert [event.sequence for event in record.events] == list(range(len(record.events)))


def test_time_has_no_accumulated_error() -> None:
    # 3,600 s is 72,000 cycles of 50 ms, and 72,000 · 50 / 1000 is exact.
    seen: list[float] = []
    source = ExplicitOrders([])
    simulate_stepped(
        warehouse(), source, 1, 3600.0, 50, on_cycle=lambda cycle, time_s: seen.append(time_s)
    )
    assert len(seen) == 72001
    assert seen[-1] == 3600.0
    assert seen[1] == 0.05
    assert seen[7] == 7 * 50 / 1000


def test_cycle_order_is_order_handling_controller_plant() -> None:
    seen: list[tuple[str, int]] = []

    class Spy:
        def scan(self, signals: Mapping[int, CraneSignals]) -> None:
            crane = signals[1]
            seen.append(("job", crane.job_id))
            seen.append(("actual", int(crane.horizontal_actual_m)))
            crane.horizontal_target_m = 20.0
            crane.horizontal_start = True

    source = ExplicitOrders([OrderRequest(0.0, "storage", "A")])
    simulate_stepped(warehouse(), source, 1, 0.2, 100, controller=Spy())
    # A job written in cycle 0 is seen in cycle 0, so order handling comes first.
    assert seen[0] == ("job", 1)
    assert seen[1] == ("actual", 0)


def test_arrival_between_boundaries_takes_effect_at_the_next_and_keeps_its_time() -> None:
    record = run([(0.05, "storage", "A")])
    assert record.orders[0].arrival_s == 0.05
    assert record.orders[0].start_s == pytest.approx(0.1)
    assert record.events[0].kind == "order_arrived"
    assert record.events[0].time_s == pytest.approx(0.1)


def test_next_order_starts_in_the_cycle_the_last_one_completes() -> None:
    record = run([(0.0, "storage", "A"), (0.0, "storage", "A")])
    first, second = record.orders
    assert second.start_s == first.completion_s


def test_open_orders_get_the_same_reasons_as_event_based_runs() -> None:
    record = run([(0.0, "storage", "A"), (1.0, "storage", "A")], duration_s=5.0)
    assert [(order.outcome, order.reason) for order in record.orders] == [
        ("unfinished", "run_ended"),
        ("unfinished", "run_ended"),
    ]


def test_nothing_happens_after_the_duration() -> None:
    record = run([(0.0, "storage", "A")], duration_s=5.05)
    assert all(event.time_s <= 5.05 for event in record.events)


def test_arrival_after_the_last_cycle_start_is_still_processed() -> None:
    record = run([(5.03, "storage", "A")], duration_s=5.05)
    assert [order.arrival_s for order in record.orders] == [5.03]
    assert record.orders[0].outcome == "unfinished"
    assert record.orders[0].location is not None


def test_order_completing_at_the_last_cycle_counts() -> None:
    assert run([(0.0, "storage", "A")], duration_s=23.0).orders[0].outcome == "completed"
    assert run([(0.0, "storage", "A")], duration_s=22.9).orders[0].outcome == "unfinished"


def test_empty_scenario_works() -> None:
    record = run([], duration_s=10.0)
    assert record.orders == ()
    assert record.events == ()
    assert record.crane_count == 1
    assert record.cell_count == 10


def test_unfulfillable_retrieval_moves_nothing() -> None:
    record = run([(0.0, "retrieval", "A")])
    assert record.orders[0].outcome == "unfulfillable"
    assert "activity_started" not in kinds(record)


def test_controller_doing_nothing_leaves_a_backlog() -> None:
    class Idle:
        def scan(self, signals: Mapping[int, CraneSignals]) -> None:
            pass

    record = run([(0.0, "storage", "A")], duration_s=60.0, controller=Idle())
    assert record.orders[0].outcome == "unfinished"
    assert record.orders[0].reason == "run_ended"


def test_generated_scenario_is_reproducible_and_finishes_orders() -> None:
    def once() -> RunRecord:
        source = GeneratedOrders(7, 60.0, 1.0, {"A": 1.0})
        return simulate_stepped(warehouse(), source, 7, 300.0, 100).record

    first, second = once(), once()
    assert first.events == second.events
    assert first.orders == second.orders
    assert any(order.outcome == "completed" for order in first.orders)


def test_load_units_are_counted_as_in_the_plant() -> None:
    record = run([(0.0, "storage", "A"), (40.0, "retrieval", "A")])
    assert [order.outcome for order in record.orders] == ["completed", "completed"]
    assert record.initial_occupied == 0


def test_no_files_network_or_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("simulate_stepped must not use this")

    with monkeypatch.context() as patch:
        patch.setattr(builtins, "open", forbidden)
        patch.setattr(socket, "socket", forbidden)
        patch.setattr(time, "time", forbidden)
        patch.setattr(time, "monotonic", forbidden)
        patch.setattr(time, "perf_counter", forbidden)
        record = run([(0.0, "storage", "A")], duration_s=30.0)
    assert record.orders[0].outcome == "completed"


def test_short_move_uses_the_same_time_as_the_hand_calculation() -> None:
    assert math.ceil(2.0 * math.sqrt(2.0) / 0.1) == 29


def test_a_step_ending_after_the_duration_has_no_effect() -> None:
    # A pick from 0 s ends at 10 s, which is after a duration of 9.95 s.
    record = run([(0.0, "storage", "A")], duration_s=9.95, cycle_ms=50)
    assert "load_picked" not in kinds(record)
    assert all(event.time_s <= 9.95 for event in record.events)


class WrongPlaces:
    """Picks at the job's source unless told otherwise, and sets at a chosen horizontal position."""

    def __init__(self, pick_at_m: float | None, set_at_m: float) -> None:
        self.pick_at_m = pick_at_m
        self.set_at_m = set_at_m
        self.step = 0

    def scan(self, signals: Mapping[int, CraneSignals]) -> None:
        crane = signals[1]
        crane.horizontal_start = crane.pick_start = crane.set_start = False
        at_rest = crane.horizontal_in_position and not crane.handling_active
        if self.step == 0 and crane.job_id:
            self.step = 1
            target = crane.source_horizontal_m if self.pick_at_m is None else self.pick_at_m
            crane.horizontal_target_m = target
            crane.horizontal_start = True
        elif self.step == 1 and at_rest:
            self.step = 2
            crane.side = 1
            crane.pick_start = True
        elif self.step == 2 and crane.load_present:
            self.step = 3
            crane.horizontal_target_m = self.set_at_m
            crane.horizontal_start = True
        elif self.step == 3 and at_rest:
            self.step = 4
            crane.side = 1
            crane.set_start = True
        elif self.step == 4 and not crane.load_present:
            crane.job_done_id = crane.job_id


def test_a_load_set_at_another_place_completes_no_order() -> None:
    # The job's cell is bay 1, at 2 m. This controller sets at bay 2, at 6 m, then reports done.
    controller = WrongPlaces(None, 6.0)
    record = run([(0.0, "storage", "A")], duration_s=120.0, controller=controller)
    assert controller.step == 4
    assert "load_set" not in kinds(record)
    assert record.orders[0].outcome == "unfinished"


def test_a_load_picked_at_another_place_completes_no_order() -> None:
    # Retrieval picks the oldest unit in bay 1, at 2 m. This controller picks bay 2, at 6 m.
    content = minimal_warehouse_dict()
    content["initial_stock"] = [
        {"location": {"aisle": 1, "rack": 1, "bay": bay, "level": 1}, "article": "A"}
        for bay in (1, 2)
    ]
    controller = WrongPlaces(6.0, 20.0)
    source = ExplicitOrders([OrderRequest(0.0, "retrieval", "A")])
    record = simulate_stepped(
        WarehouseDefinition.model_validate(content), source, 1, 120.0, 100, controller
    ).record
    assert controller.step == 4
    assert "load_picked" not in kinds(record)
    assert record.orders[0].outcome == "unfinished"


class StopsAtCycle:
    """Behaves as the built-in controller, then stops the run or fails in a given cycle."""

    def __init__(self, cycle: int, error: Exception) -> None:
        self._built_in = BuiltInController()
        self._cycle = cycle
        self._error = error
        self._cycles_seen = 0

    def scan(self, signals: Mapping[int, CraneSignals]) -> None:
        if self._cycles_seen == self._cycle:
            raise self._error
        self._cycles_seen += 1
        self._built_in.scan(signals)


STOPPED = ControllerStopped("connection_lost", "the connection was lost")


def stepped_until(cycle: int, error: Exception = STOPPED) -> Any:
    source = ExplicitOrders(
        [OrderRequest(0.0, "storage", "A"), OrderRequest(1000.0, "storage", "A")]
    )
    controller = StopsAtCycle(cycle, error)
    return simulate_stepped(warehouse(), source, 1, 3600.0, 100, controller)


def test_a_stopped_run_returns_what_was_recorded_with_the_stop() -> None:
    run = stepped_until(50)
    assert run.stop.reason == "connection_lost"
    assert run.stop.message == "the connection was lost"
    assert run.stop.cycle == 50
    assert run.stop.time_s == 5.0
    assert kinds(run.record)[:3] == ["order_arrived", "order_queued", "order_started"]


def test_a_stopped_run_lasts_as_long_as_was_simulated() -> None:
    assert stepped_until(50).record.duration_s == 5.0


def test_a_stop_in_the_first_cycle_lasts_one_cycle_so_that_metrics_can_be_calculated() -> None:
    assert stepped_until(0).record.duration_s == 0.1


def test_orders_that_would_arrive_after_the_stop_are_not_added() -> None:
    assert len(stepped_until(50).record.orders) == 1


def test_an_order_in_progress_at_the_stop_is_unfinished() -> None:
    order = stepped_until(50).record.orders[0]
    assert order.outcome == "unfinished"
    assert order.reason == "run_ended"


def test_the_plant_does_not_advance_after_the_stop() -> None:
    cycles: list[int] = []
    source = ExplicitOrders([OrderRequest(0.0, "storage", "A")])
    controller = StopsAtCycle(3, STOPPED)
    simulate_stepped(
        warehouse(),
        source,
        1,
        3600.0,
        100,
        controller,
        on_cycle=lambda cycle, time_s: cycles.append(cycle),
    )
    assert cycles == [0, 1, 2]


def test_any_other_exception_still_raises_a_controller_error() -> None:
    with pytest.raises(ControllerError, match="cycle 5"):
        stepped_until(5, ValueError("broken"))


def test_a_run_with_no_stop_has_empty_stop_information() -> None:
    source = ExplicitOrders([OrderRequest(0.0, "storage", "A")])
    assert simulate_stepped(warehouse(), source, 1, 100.0, 100).stop is None
