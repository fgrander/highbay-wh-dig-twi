import json
from pathlib import Path
from typing import Any

import pytest

from conftest import minimal_warehouse_dict
from highbay_sim.config import WarehouseDefinition
from highbay_sim.engine import RunRecord, simulate
from highbay_sim.events import OrderType, SimulationEvent
from highbay_sim.metrics import calculate_metrics
from highbay_sim.orders import ExplicitOrders, OrderRequest
from highbay_sim.outputs import RunInfo, result_document
from highbay_sim.replay import build_replay, first_backlog_peak_s, replay_text

INFO = RunInfo("9.9.9", 7, "w", "a" * 64, "s", "b" * 64, 3600.0)


def stocked_warehouse() -> WarehouseDefinition:
    content = minimal_warehouse_dict()
    content["initial_stock"] = [
        {"location": {"aisle": 1, "rack": 1, "bay": 2, "level": 1}, "article": "C"},
        {"location": {"aisle": 1, "rack": 1, "bay": 1, "level": 1}, "article": "B"},
    ]
    return WarehouseDefinition.model_validate(content)


def replay_of(
    warehouse: WarehouseDefinition,
    orders: list[tuple[float, OrderType, str]],
    duration_s: float = 3600.0,
    warmup_s: float = 0.0,
) -> tuple[dict[str, Any], dict[str, Any]]:
    record = simulate(
        warehouse, ExplicitOrders([OrderRequest(*order) for order in orders]), 7, duration_s
    )
    metrics = calculate_metrics(record, warmup_s)
    info = RunInfo("9.9.9", 7, "w", "a" * 64, "s", "b" * 64, duration_s)
    return build_replay(record, warehouse, info, metrics), result_document(info, metrics)


@pytest.fixture
def replay_and_result() -> tuple[dict[str, Any], dict[str, Any]]:
    return replay_of(stocked_warehouse(), [(0.0, "storage", "A"), (100.0, "retrieval", "A")])


def test_top_level_parts_and_version(replay_and_result: tuple[dict, dict]) -> None:
    replay, _ = replay_and_result
    assert replay["format_version"] == 1
    assert set(replay) == {
        "format_version",
        "run",
        "warehouse",
        "articles",
        "initial_stock",
        "order_columns",
        "orders",
        "event_columns",
        "events",
        "reported",
    }


def test_run_equals_the_results_run_block(replay_and_result: tuple[dict, dict]) -> None:
    replay, result = replay_and_result
    assert replay["run"] == result["run"]


def test_warehouse_part_has_one_entry_per_aisle_including_overrides() -> None:
    content = minimal_warehouse_dict()
    content["layout"]["aisle_count"] = 2
    content["transfer_points"]["aisles"] = {2: {"left": ["outbound"], "right": ["inbound"]}}
    replay, _ = replay_of(WarehouseDefinition.model_validate(content), [])
    warehouse = replay["warehouse"]
    assert warehouse["layout"]["aisle_count"] == 2
    assert warehouse["layout"]["cell"] == {"height_m": 3.0, "length_m": 4.0, "width_m": 1.5}
    assert warehouse["crane"]["pick_time_s"] == 10.0
    assert warehouse["transfer_points"] == {
        "1": {"left": ["inbound"], "right": ["outbound"]},
        "2": {"left": ["outbound"], "right": ["inbound"]},
    }
    assert warehouse["crane_start_positions"] == {"1": [0.0, 0.0], "2": [20.0, 0.0]}


def test_articles_and_initial_stock(replay_and_result: tuple[dict, dict]) -> None:
    replay, _ = replay_and_result
    assert replay["articles"] == ["A", "B", "C"]
    assert replay["initial_stock"] == [[1, 1, 1, 1, 1], [1, 1, 2, 1, 2]]


def test_order_rows_follow_their_columns(replay_and_result: tuple[dict, dict]) -> None:
    replay, _ = replay_and_result
    assert replay["order_columns"] == [
        "order_id",
        "type",
        "article",
        "arrival_s",
        "start_s",
        "completion_s",
        "crane",
        "location",
        "transfer_point",
        "outcome",
        "reason",
    ]
    assert replay["orders"][0] == [
        "O000001",
        "storage",
        0,
        0.0,
        0.0,
        replay["orders"][0][5],
        1,
        [1, 1, 1, 2],
        "left",
        "completed",
        "",
    ]


def test_empty_order_values_are_null_except_reason() -> None:
    replay, _ = replay_of(stocked_warehouse(), [(5.0, "retrieval", "MISSING")])
    assert replay["orders"][0] == [
        "O000001",
        "retrieval",
        replay["articles"].index("MISSING"),
        5.0,
        None,
        None,
        None,
        None,
        None,
        "unfulfillable",
        "no_stock",
    ]


def test_event_rows_follow_their_columns(replay_and_result: tuple[dict, dict]) -> None:
    replay, _ = replay_and_result
    assert replay["event_columns"] == [
        "time_s",
        "kind",
        "order",
        "crane",
        "location",
        "activity",
        "end_s",
        "start_position",
        "target_position",
    ]
    rows = replay["events"]
    assert rows[0] == [0.0, "order_arrived", 0, None, None, None, None, None, None]
    moving = next(row for row in rows if row[5] == "moving_loaded")
    assert moving[1] == "activity_started"
    assert moving[3] == 1
    assert moving[4] == [1, 1, 1, 2]
    assert moving[7] == [0.0, 0.0]
    assert moving[8] == [2.0, 3.0]
    handling = next(row for row in rows if row[5] == "handling")
    assert handling[7] is None
    assert handling[8] is None


def test_times_are_not_rounded() -> None:
    # 2 m with speed 2 m/s and acceleration 1 m/s² takes 2·sqrt(2) s, with many decimals.
    record = simulate(
        stocked_warehouse(),
        ExplicitOrders([OrderRequest(0.0, "retrieval", "B")]),
        7,
        3600.0,
    )
    replay = build_replay(record, stocked_warehouse(), INFO, calculate_metrics(record, 0.0))
    read_back = json.loads(replay_text(replay))
    expected = [event.end_s for event in record.events if event.kind == "activity_started"]
    actual = [row[6] for row in read_back["events"] if row[1] == "activity_started"]
    assert actual == expected
    assert any(value != round(value, 3) for value in actual)

    event_times = [row[0] for row in read_back["events"]]
    assert event_times == [event.time_s for event in record.events]
    assert any(value != round(value, 3) for value in event_times)

    completion = read_back["orders"][0][5]
    assert completion == record.orders[0].completion_s
    assert completion != round(completion, 3)


def test_reported_equals_the_results_metrics(replay_and_result: tuple[dict, dict]) -> None:
    replay, result = replay_and_result
    reported = replay["reported"]
    for name in ("backlog_orders", "storage_occupancy", "order_outcomes"):
        assert reported[name] == result["metrics"][name]


def test_text_is_compact_and_ends_with_one_newline(replay_and_result: tuple[dict, dict]) -> None:
    text = replay_text(replay_and_result[0])
    assert text.endswith("}\n")
    assert text.count("\n") == 1
    assert '": ' not in text
    assert ", " not in text.split('"events"')[1].split("]")[0]


def event(time_s: float, kind: Any, order_id: str = "O000001") -> SimulationEvent:
    return SimulationEvent(time_s, 0, kind, order_id, "storage")


def record_of(*events: SimulationEvent, duration_s: float = 100.0) -> RunRecord:
    return RunRecord(tuple(events), (), duration_s, 10, 1, 0)


def test_peak_inside_the_window() -> None:
    record = record_of(
        event(20.0, "order_arrived"),
        event(30.0, "order_arrived"),
        event(40.0, "order_started"),
    )
    assert first_backlog_peak_s(record, 10.0, 2) == 30.0


def test_peak_carried_in_from_before_the_window() -> None:
    record = record_of(event(1.0, "order_arrived"), event(50.0, "order_started"))
    assert first_backlog_peak_s(record, 10.0, 1) == 10.0


def test_first_of_several_times_with_the_maximum() -> None:
    record = record_of(
        event(20.0, "order_arrived"),
        event(30.0, "order_started"),
        event(40.0, "order_arrived"),
    )
    assert first_backlog_peak_s(record, 10.0, 1) == 20.0


def test_order_started_on_arrival_is_not_a_peak() -> None:
    record = record_of(
        event(20.0, "order_arrived"),
        event(20.0, "order_started"),
        event(30.0, "order_arrived"),
    )
    assert first_backlog_peak_s(record, 10.0, 1) == 30.0


def test_no_backlog_gives_the_window_start() -> None:
    assert first_backlog_peak_s(record_of(), 10.0, 0) == 10.0


def test_peak_time_matches_the_reported_maximum() -> None:
    replay, result = replay_of(
        stocked_warehouse(),
        [(0.0, "storage", "A"), (1.0, "storage", "A"), (2.0, "storage", "A")],
        warmup_s=0.5,
    )
    assert result["metrics"]["backlog_orders"]["max_in_window"] == 2
    assert replay["reported"]["first_backlog_peak_s"] == 2.0


def test_replay_file_can_be_written(tmp_path: Path, replay_and_result: tuple[dict, dict]) -> None:
    from highbay_sim.replay import write_replay

    path = tmp_path / "replay.json"
    write_replay(path, replay_and_result[0])
    assert b"\r" not in path.read_bytes()
    assert json.loads(path.read_text(encoding="utf-8")) == json.loads(
        json.dumps(replay_and_result[0])
    )
