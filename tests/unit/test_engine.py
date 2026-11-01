import builtins
import math
import socket
import time
from typing import Any

import pytest

from conftest import minimal_warehouse_dict
from highbay_sim.config import WarehouseDefinition
from highbay_sim.engine import OrderRecord, RunRecord, simulate
from highbay_sim.events import OrderType, SimulationEvent
from highbay_sim.orders import ExplicitOrders, GeneratedOrders, OrderRequest

ALL_CELLS = [(1, 1, bay, level) for bay in range(1, 6) for level in range(1, 3)]
SHORT_MOVE = 2.0 * math.sqrt(2.0)  # 2 m with speed 2 m/s and acceleration 1 m/s²


def warehouse(
    stock: dict[tuple[int, int, int, int], str] | None = None,
    default: dict[str, list[str]] | None = None,
    aisle_count: int = 1,
) -> WarehouseDefinition:
    content = minimal_warehouse_dict()
    content["layout"]["aisle_count"] = aisle_count
    if default is not None:
        content["transfer_points"]["default"] = default
    content["initial_stock"] = [
        {
            "location": dict(zip(("aisle", "rack", "bay", "level"), location, strict=True)),
            "article": article,
        }
        for location, article in (stock or {}).items()
    ]
    return WarehouseDefinition.model_validate(content)


def full_except(*free: tuple[int, int, int, int]) -> dict[tuple[int, int, int, int], str]:
    return {location: "B" for location in ALL_CELLS if location not in free}


def run(
    wh: WarehouseDefinition,
    orders: list[tuple[float, OrderType, str]],
    duration_s: float = 3600.0,
    **options: Any,
) -> RunRecord:
    requests = [OrderRequest(*order) for order in orders]
    return simulate(wh, ExplicitOrders(requests), 1, duration_s, **options)


def order(record: RunRecord, number: int) -> OrderRecord:
    return record.orders[number - 1]


def activities(record: RunRecord, order_id: str) -> list[tuple[str, float, float]]:
    return [
        (event.activity or "", event.time_s, event.end_s or 0.0)
        for event in record.events
        if event.kind == "activity_started" and event.order_id == order_id
    ]


def test_storage_cycle_steps() -> None:
    record = run(warehouse(full_except((1, 1, 3, 2))), [(0.0, "storage", "A")])
    assert activities(record, "O000001") == [
        ("moving_empty", 0.0, pytest.approx(0.0)),
        ("handling", 0.0, pytest.approx(10.0)),
        ("moving_loaded", pytest.approx(10.0), pytest.approx(17.0)),
        ("handling", pytest.approx(17.0), pytest.approx(27.0)),
    ]
    stored = order(record, 1)
    assert stored.outcome == "completed"
    assert stored.location == (1, 1, 3, 2)
    assert stored.crane == 1
    assert stored.transfer_point == "left"
    assert stored.start_s == 0.0
    assert stored.completion_s == pytest.approx(27.0)


def test_retrieval_cycle_steps() -> None:
    record = run(warehouse({(1, 1, 3, 2): "A"}), [(30.0, "retrieval", "A")])
    assert activities(record, "O000001") == [
        ("moving_empty", 30.0, pytest.approx(37.0)),
        ("handling", pytest.approx(37.0), pytest.approx(47.0)),
        ("moving_loaded", pytest.approx(47.0), pytest.approx(54.0)),
        ("handling", pytest.approx(54.0), pytest.approx(64.0)),
    ]
    retrieved = order(record, 1)
    assert retrieved.outcome == "completed"
    assert retrieved.transfer_point == "right"
    assert retrieved.completion_s == pytest.approx(64.0)


def test_load_events_name_the_cell_only_when_a_cell_is_involved() -> None:
    record = run(
        warehouse(full_except((1, 1, 3, 2))),
        [(0.0, "storage", "A"), (30.0, "retrieval", "A")],
    )
    loads = [
        (event.kind, event.order_id, event.location)
        for event in record.events
        if event.kind in ("load_picked", "load_set")
    ]
    assert loads == [
        ("load_picked", "O000001", None),
        ("load_set", "O000001", (1, 1, 3, 2)),
        ("load_picked", "O000002", (1, 1, 3, 2)),
        ("load_set", "O000002", None),
    ]


def test_crane_starts_at_first_inbound_point_left_before_right() -> None:
    both = {"left": ["inbound"], "right": ["inbound", "outbound"]}
    record = run(warehouse(default=both), [(0.0, "storage", "A")])
    assert activities(record, "O000001")[0][2] == pytest.approx(0.0)
    assert order(record, 1).transfer_point == "left"


def test_crane_starts_at_right_end_when_it_is_the_only_inbound_point() -> None:
    right_only = {"left": ["outbound"], "right": ["inbound"]}
    record = run(warehouse(full_except((1, 1, 5, 1)), default=right_only), [(0.0, "storage", "A")])
    assert activities(record, "O000001")[0][2] == pytest.approx(0.0)
    assert order(record, 1).transfer_point == "right"
    assert order(record, 1).completion_s == pytest.approx(10.0 + SHORT_MOVE + 10.0)


def test_crane_stays_at_last_position_between_orders() -> None:
    stock = {**full_except((1, 1, 3, 2), (1, 1, 1, 1)), (1, 1, 1, 1): "C"}
    record = run(
        warehouse(stock),
        [(0.0, "storage", "A"), (100.0, "retrieval", "C")],
    )
    # From the cell at (10, 3), where the storage order ended, to the cell at (2, 0).
    empty_move = 8.0 / 2.0 + 2.0 / 1.0
    assert activities(record, "O000002")[0] == (
        "moving_empty",
        100.0,
        pytest.approx(100.0 + empty_move),
    )


def test_orders_are_served_first_come_first_served_per_crane() -> None:
    record = run(
        warehouse(full_except((1, 1, 1, 1), (1, 1, 5, 2))),
        [(0.0, "storage", "A"), (1.0, "storage", "B")],
    )
    first, second = order(record, 1), order(record, 2)
    assert first.completion_s is not None
    assert second.start_s == pytest.approx(first.completion_s)


def test_aisles_work_independently() -> None:
    record = run(
        warehouse({(1, 1, 3, 2): "A", (2, 1, 3, 2): "C"}, aisle_count=2),
        [(0.0, "retrieval", "A"), (0.0, "retrieval", "C")],
    )
    assert order(record, 1).crane == 1
    assert order(record, 2).crane == 2
    assert order(record, 2).start_s == 0.0


def test_two_outbound_points_use_the_nearer_one() -> None:
    both = {"left": ["inbound", "outbound"], "right": ["inbound", "outbound"]}
    record = run(warehouse({(1, 1, 5, 1): "A"}, default=both), [(0.0, "retrieval", "A")])
    assert order(record, 1).transfer_point == "right"


def test_two_inbound_points_use_shortest_total_travel_from_crane_position() -> None:
    both = {"left": ["inbound", "outbound"], "right": ["inbound", "outbound"]}
    stock = {**full_except((1, 1, 5, 2)), (1, 1, 5, 1): "A"}
    record = run(
        warehouse(stock, default=both),
        [(0.0, "retrieval", "A"), (100.0, "storage", "D")],
    )
    # The retrieval leaves the crane at the right end, so storing via the right is shortest.
    assert order(record, 1).transfer_point == "right"
    assert order(record, 2).transfer_point == "right"


def test_equal_travel_uses_the_left_end() -> None:
    both = {"left": ["inbound", "outbound"], "right": ["inbound", "outbound"]}
    record = run(warehouse({(1, 1, 3, 1): "A"}, default=both), [(0.0, "retrieval", "A")])
    assert order(record, 1).transfer_point == "left"


def test_retrieval_without_stock_is_unfulfillable_and_run_continues() -> None:
    record = run(
        warehouse({(1, 1, 3, 2): "C"}),
        [(0.0, "retrieval", "MISSING"), (1.0, "retrieval", "C")],
    )
    missing = order(record, 1)
    assert missing.outcome == "unfulfillable"
    assert missing.reason == "no_stock"
    assert missing.start_s is None
    assert order(record, 2).outcome == "completed"


def test_stock_is_available_only_after_set_down() -> None:
    record = run(
        warehouse(),
        [(0.0, "storage", "A"), (5.0, "retrieval", "A"), (100.0, "retrieval", "A")],
    )
    assert order(record, 2).outcome == "unfulfillable"
    assert order(record, 3).outcome == "completed"


def test_storage_with_no_free_cell_waits_until_a_cell_is_released_at_pick_up() -> None:
    record = run(
        warehouse(full_except()),
        [(0.0, "storage", "A"), (10.0, "retrieval", "B")],
    )
    waiting = order(record, 1)
    retrieval = order(record, 2)
    assert [e.kind for e in record.events if e.order_id == "O000001"][:2] == [
        "order_arrived",
        "order_waiting_for_cell",
    ]
    picked = next(
        e.time_s for e in record.events if e.kind == "load_picked" and e.order_id == "O000002"
    )
    queued = next(
        e.time_s for e in record.events if e.kind == "order_queued" and e.order_id == "O000001"
    )
    assert picked == pytest.approx(10.0 + SHORT_MOVE + 10.0)
    assert queued == pytest.approx(picked)
    assert waiting.location == retrieval.location == (1, 1, 1, 1)
    assert waiting.start_s == pytest.approx(retrieval.completion_s)
    assert waiting.outcome == "completed"


def test_storage_still_waiting_at_end_is_unfinished_with_reason() -> None:
    record = run(warehouse(full_except()), [(0.0, "storage", "A")])
    assert order(record, 1).outcome == "unfinished"
    assert order(record, 1).reason == "no_free_cell"


def test_open_orders_at_the_end_are_unfinished() -> None:
    record = run(
        warehouse({(1, 1, 3, 2): "A", (1, 1, 2, 2): "C"}),
        [(0.0, "retrieval", "A"), (1.0, "retrieval", "C")],
        duration_s=5.0,
    )
    running, queued = order(record, 1), order(record, 2)
    assert running.outcome == "unfinished"
    assert running.reason == "run_ended"
    assert running.start_s == 0.0
    assert running.completion_s is None
    assert queued.outcome == "unfinished"
    assert queued.reason == "run_ended"
    assert queued.start_s is None


def test_completed_order_has_no_reason() -> None:
    record = run(warehouse(), [(0.0, "storage", "A")])
    assert order(record, 1).reason == ""


def test_order_completing_exactly_at_the_end_counts() -> None:
    record = run(
        warehouse(full_except((1, 1, 3, 2))),
        [(0.0, "storage", "A")],
        duration_s=27.0,
    )
    assert order(record, 1).outcome == "completed"


def test_scenario_without_orders_completes() -> None:
    record = run(warehouse({(1, 1, 1, 1): "A"}), [])
    assert record.orders == ()
    assert record.events == ()
    assert record.cell_count == 10
    assert record.crane_count == 1
    assert record.initial_occupied == 1


def test_order_ids_follow_arrival_order() -> None:
    record = run(warehouse(), [(5.0, "storage", "A"), (1.0, "storage", "B")])
    assert [(o.order_id, o.article) for o in record.orders] == [
        ("O000001", "B"),
        ("O000002", "A"),
    ]


def generated_run(seed: int = 3, **options: Any) -> RunRecord:
    content = minimal_warehouse_dict()
    content["layout"].update(aisle_count=3, racks_per_aisle=2, bays_per_rack=10, levels_per_rack=5)
    wh = WarehouseDefinition.model_validate(content).model_copy(
        update={"storage_rule": "random_free"}
    )
    source = GeneratedOrders(seed, 300.0, 0.6, {"A": 1.0, "B": 1.0})
    return simulate(wh, source, seed, 3600.0, **options)


def test_same_inputs_give_same_events_and_orders() -> None:
    first, second = generated_run(), generated_run()
    assert first.events == second.events
    assert first.orders == second.orders
    assert first.orders != ()


def test_different_seed_gives_different_events() -> None:
    assert generated_run(seed=3).events != generated_run(seed=4).events


def test_results_do_not_depend_on_on_event() -> None:
    seen: list[SimulationEvent] = []
    observed = generated_run(on_event=seen.append)
    assert observed == generated_run()
    assert tuple(seen) == observed.events


def test_events_are_immutable_and_in_order() -> None:
    record = generated_run()
    with pytest.raises(AttributeError):
        record.events[0].time_s = 1.0  # type: ignore[misc]
    times = [event.time_s for event in record.events]
    assert times == sorted(times)
    assert [event.sequence for event in record.events] == list(range(len(record.events)))


def test_simulate_needs_no_files_network_or_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("simulate must not use this")

    with monkeypatch.context() as patch:
        patch.setattr(builtins, "open", forbidden)
        patch.setattr(socket, "socket", forbidden)
        patch.setattr(time, "time", forbidden)
        patch.setattr(time, "monotonic", forbidden)
        patch.setattr(time, "perf_counter", forbidden)
        record = generated_run()
    assert record.orders != ()
