"""State from a recording, by the same rules as the browser viewer's replay-state.js."""

import json
import random
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest

from conftest import SAMPLES, replay_data
from highbay.replay.core.recorded_source import RecordedSource, open_recording
from highbay.replay.core.state_source import INTERFACE_VERSION, StateSource, StateSourceError

COLUMNS = (
    "time_s",
    "kind",
    "order",
    "crane",
    "location",
    "activity",
    "end_s",
    "start_position",
    "target_position",
)


def event(time_s: float, kind: str, **fields: Any) -> list[Any]:
    return [time_s, kind, *(fields.get(column) for column in COLUMNS[2:])]


CELL = [1, 1, 3, 2]
STOCK_CELL = (1, 2, 1, 1)
WAREHOUSE = {
    "layout": {
        "aisle_count": 1,
        "racks_per_aisle": 2,
        "bays_per_rack": 5,
        "levels_per_rack": 2,
        "cell": {"height_m": 3.0, "length_m": 4.0, "width_m": 1.5},
    },
    "crane": {
        "horizontal": {"speed_m_s": 2.0, "acceleration_m_s2": 1.0},
        "vertical": {"speed_m_s": 1.0, "acceleration_m_s2": 1.0},
        "pick_time_s": 10.0,
        "set_time_s": 10.0,
    },
    "transfer_points": {"1": {"left": ["inbound"], "right": ["outbound"]}},
    "crane_start_positions": {"1": [0.0, 0.0]},
}


def recording(events: list[list[Any]] | None = None) -> dict[str, Any]:
    return {
        "format_version": 1,
        "run": {
            "software_version": "0.4.0",
            "seed": 1,
            "warehouse": {"name": "w", "sha256": "a"},
            "scenario": {"name": "s", "sha256": "b"},
            "duration_s": 100.0,
            "window": {"start_s": 10.0, "end_s": 100.0},
        },
        "warehouse": WAREHOUSE,
        "articles": ["a", "b"],
        "initial_stock": [[1, 2, 1, 1, 1]],
        "order_columns": [],
        "orders": [
            ["O1", "storage", 0, 1.0, 2.0, 40.0, 1, CELL, "left", "completed", ""],
            ["O2", "retrieval", 1, 3.0, None, None, 1, list(STOCK_CELL), None, "unfinished", ""],
        ],
        "event_columns": list(COLUMNS),
        "events": events if events is not None else [],
        "reported": {
            "backlog_orders": {"at_window_end": 0, "max_in_window": 1},
            "first_backlog_peak_s": 10.0,
        },
    }


def storage_events() -> list[list[Any]]:
    return [
        event(1.0, "order_arrived", order=0),
        event(1.0, "order_queued", order=0, crane=1, location=CELL),
        event(2.0, "order_started", order=0, crane=1, location=CELL),
        event(2.0, "activity_started", order=0, crane=1, activity="handling", end_s=12.0),
        event(12.0, "load_picked", order=0, crane=1),
        event(
            12.0,
            "activity_started",
            order=0,
            crane=1,
            activity="moving_loaded",
            end_s=21.0,
            start_position=[0.0, 0.0],
            target_position=[10.0, 3.0],
        ),
        event(21.0, "activity_started", order=0, crane=1, activity="handling", end_s=31.0),
        event(31.0, "load_set", order=0, crane=1, location=CELL),
        event(31.0, "order_completed", order=0, crane=1),
    ]


def source(events: list[list[Any]] | None = None) -> RecordedSource:
    return RecordedSource(recording(events))


def test_follows_the_interface() -> None:
    assert INTERFACE_VERSION == 1
    instance = source()
    assert isinstance(instance, StateSource)
    assert instance.can_move_backward
    assert instance.range_is_final
    assert instance.time_range() == (0.0, 100.0)


def test_description_gives_what_a_scene_needs() -> None:
    description = source().describe()
    assert description.layout == WAREHOUSE["layout"]
    assert description.crane == WAREHOUSE["crane"]
    assert description.transfer_points == WAREHOUSE["transfer_points"]
    assert description.crane_start_positions == WAREHOUSE["crane_start_positions"]
    assert description.articles == ["a", "b"]
    assert description.run["seed"] == 1
    assert description.reported is not None
    assert description.reported["first_backlog_peak_s"] == 10.0


def test_start_of_a_run_shows_initial_stock() -> None:
    state = source().state_at(0.0)
    assert state.time_s == 0.0
    assert not state.in_measurement_window
    assert state.occupied_cells == 1
    assert state.occupancy == pytest.approx(1 / 20)
    assert state.cranes[1].activity == "idle"
    assert state.cranes[1].position == (0.0, 0.0)
    assert source().cell(STOCK_CELL).state == "occupied"


def test_stored_load_units_are_in_location_order() -> None:
    instance = source(storage_events())
    instance.state_at(50.0)
    assert [load.location for load in instance.stored_load_units()] == [(1, 1, 3, 2), STOCK_CELL]


def test_order_counts_and_backlog_follow_the_events() -> None:
    instance = source(storage_events())
    state = instance.state_at(1.5)
    assert state.arrived == 1
    assert state.backlog.total == 1
    assert state.backlog.per_aisle == {1: 1}
    assert instance.cell(tuple(CELL)).state == "reserved_for_storage"

    state = instance.state_at(2.0)
    assert state.backlog.total == 0
    assert state.backlog.per_aisle == {1: 0}

    state = instance.state_at(40.0)
    assert state.completed == 1


def test_waiting_for_a_cell_and_unfulfillable_orders() -> None:
    instance = source(
        [
            event(1.0, "order_arrived", order=0),
            event(1.0, "order_waiting_for_cell", order=0),
            event(3.0, "order_arrived", order=1),
            event(4.0, "order_unfulfillable", order=1),
            event(5.0, "order_queued", order=0, crane=1, location=CELL),
        ]
    )
    state = instance.state_at(3.0)
    assert state.backlog.waiting_for_cell == 1
    assert state.backlog.total == 2

    state = instance.state_at(4.0)
    assert state.unfulfillable == 1
    assert state.backlog.total == 1

    assert instance.state_at(5.0).backlog.waiting_for_cell == 0


def test_a_load_from_an_aisle_end_travels_and_is_stored() -> None:
    instance = source(storage_events())
    state = instance.state_at(15.0)
    assert state.cranes[1].carrying == "o0"
    assert state.cranes[1].activity == "moving_loaded"
    assert state.cranes[1].order == 0
    assert state.cranes[1].movement_target == (10.0, 3.0)
    load = instance.load("o0")
    assert load is not None
    assert load.article == 0
    assert load.store_order == 0
    assert load.crane == 1
    assert load.location is None

    state = instance.state_at(31.0)
    assert state.cranes[1].carrying is None
    assert state.occupied_cells == 2
    stored = instance.cell(tuple(CELL)).load
    assert stored is not None
    assert stored.key == "o0"
    assert stored.crane is None
    assert stored.location == tuple(CELL)


def test_a_load_retrieved_from_a_cell_leaves_at_an_aisle_end() -> None:
    instance = source(
        [
            event(3.0, "order_arrived", order=1),
            event(3.0, "order_queued", order=1, crane=1, location=list(STOCK_CELL)),
            event(4.0, "order_started", order=1, crane=1),
            event(5.0, "load_picked", order=1, crane=1, location=list(STOCK_CELL)),
            event(9.0, "load_set", order=1, crane=1),
        ]
    )
    instance.state_at(3.0)
    assert instance.cell(STOCK_CELL).state == "reserved_for_retrieval"
    stock = instance.load("i0")
    assert stock is not None
    assert stock.retrieve_order == 1

    state = instance.state_at(5.0)
    assert state.cranes[1].carrying == "i0"
    assert state.occupied_cells == 0
    assert instance.cell(STOCK_CELL).state == "free"

    assert instance.state_at(9.0).cranes[1].carrying is None
    assert instance.load("i0") is None


def test_crane_position_during_a_movement_and_after_it() -> None:
    instance = source(storage_events())
    # At 13 s, 1 s into the movement: 0.5 m on both axes.
    assert instance.state_at(13.0).cranes[1].position == pytest.approx((0.5, 0.5))
    # Holds its target while handling, after the movement.
    assert instance.state_at(25.0).cranes[1].position == (10.0, 3.0)


def test_activity_ends_at_its_end_time() -> None:
    instance = source(storage_events())
    assert instance.state_at(5.0).cranes[1].activity == "handling"
    state = instance.state_at(31.0)
    assert state.cranes[1].activity == "idle"
    assert state.cranes[1].order is None
    assert state.cranes[1].movement_target is None


def test_measurement_window() -> None:
    assert not source().state_at(9.9).in_measurement_window
    assert source().state_at(10.0).in_measurement_window


def test_time_is_clamped_to_the_run() -> None:
    instance = source()
    assert instance.state_at(-5.0).time_s == 0.0
    assert instance.state_at(1000.0).time_s == 100.0


def test_changes_report_each_cell_once_and_then_nothing() -> None:
    instance = source(storage_events())
    instance.state_at(0.0)
    first = instance.take_changes()
    assert first.all
    assert first.cells == []

    instance.state_at(40.0)
    changes = instance.take_changes()
    assert not changes.all
    assert changes.cells == [tuple(CELL)]

    instance.state_at(50.0)
    changes = instance.take_changes()
    assert not changes.all
    assert changes.cells == []


def test_moving_backward_redraws_everything() -> None:
    instance = source(storage_events())
    instance.state_at(40.0)
    instance.take_changes()
    instance.state_at(1.0)
    assert instance.take_changes().all


def test_recording_with_no_orders_and_no_events_shows_its_stock_throughout() -> None:
    instance = source([])
    for time_s in (0.0, 50.0, 100.0):
        state = instance.state_at(time_s)
        assert state.occupied_cells == 1
        assert state.backlog.total == 0
        assert state.cranes[1].activity == "idle"


def test_damaged_structure_is_reported_when_opening(tmp_path: Path) -> None:
    content = recording()
    content["warehouse"] = {"crane": {}}
    (tmp_path / "replay.json").write_text(json.dumps(content), encoding="utf-8")
    with pytest.raises(StateSourceError, match=r"replay\.json.*damaged"):
        open_recording(tmp_path)


def test_damaged_event_is_reported_when_opening(tmp_path: Path) -> None:
    content = recording([[1.0]])
    (tmp_path / "replay.json").write_text(json.dumps(content), encoding="utf-8")
    with pytest.raises(StateSourceError, match=r"replay\.json.*damaged"):
        open_recording(tmp_path)


def snapshot(instance: RecordedSource, time_s: float) -> str:
    state = instance.state_at(time_s)
    loads = [asdict(load) for load in instance.stored_load_units()]
    return json.dumps([asdict(state), loads])


def test_same_state_however_a_time_is_reached(write_run: Callable[..., Path]) -> None:
    data = replay_data(write_run(SAMPLES / "small-warehouse.yaml", SAMPLES / "daily-scenario.yaml"))
    generator = random.Random(1)
    times = sorted(generator.uniform(0.0, data["run"]["duration_s"]) for _ in range(200))

    forward = RecordedSource(data)
    backward = RecordedSource(data)
    expected = [snapshot(forward, time_s) for time_s in times]
    actual = [snapshot(backward, time_s) for time_s in reversed(times)]
    assert expected == list(reversed(actual))

    jumping = RecordedSource(data)
    order = list(range(len(times)))
    generator.shuffle(order)
    for index in order:
        assert snapshot(jumping, times[index]) == expected[index]
