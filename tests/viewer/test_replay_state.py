"""The state at a simulated time, as in the Replay State table of data-model.md."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from conftest import (
    SAMPLES,
    Modules,
    minimal_scenario_dict,
    minimal_warehouse_dict,
    replay_data,
    write_yaml,
)

CELL = [1, 1, 3, 2]


class States:
    """Evaluates a replay's state in the browser."""

    def __init__(self, modules: Modules, data: dict[str, Any]) -> None:
        self.modules = modules
        self.data = data

    def evaluate(self, script: str, *arguments: Any) -> Any:
        return self.modules.run(
            "const { createReplayState } = await imports('replay-state.js');"
            "const state = createReplayState(args[0]);"
            f"const params = args.slice(1); {script}",
            self.data,
            *arguments,
        )

    def at(self, time_s: float) -> dict[str, Any]:
        return self.evaluate("return state.stateAt(params[0]);", time_s)

    def cell_at(self, time_s: float, location: list[int]) -> dict[str, Any]:
        return self.evaluate(
            "state.stateAt(params[0]); return state.cell(params[1]);", time_s, location
        )

    def stored_at(self, time_s: float) -> list[dict[str, Any]]:
        return self.evaluate("state.stateAt(params[0]); return state.storedLoadUnits();", time_s)


@pytest.fixture
def v1(modules: Modules, write_run: Callable[..., Path]) -> States:
    verification = SAMPLES / "verification"
    output = write_run(verification / "v1-warehouse.yaml", verification / "v1-scenario.yaml")
    return States(modules, replay_data(output))


def states_of(
    modules: Modules,
    write_run: Callable[..., Path],
    tmp_path: Path,
    warehouse: dict[str, Any],
    orders: list[dict[str, Any]],
    duration_s: float = 3600,
) -> States:
    scenario = minimal_scenario_dict()
    scenario["duration_s"] = duration_s
    scenario["orders"] = orders
    output = write_run(
        write_yaml(tmp_path / "w.yaml", warehouse), write_yaml(tmp_path / "s.yaml", scenario)
    )
    return States(modules, replay_data(output))


def stocked(*free: tuple[int, int]) -> dict[str, Any]:
    warehouse = minimal_warehouse_dict()
    warehouse["initial_stock"] = [
        {"location": {"aisle": 1, "rack": 1, "bay": bay, "level": level}, "article": "B"}
        for bay in range(1, 6)
        for level in (1, 2)
        if (bay, level) not in free
    ]
    return warehouse


def order(time_s: float, order_type: str, article: str) -> dict[str, Any]:
    return {"time_s": time_s, "type": order_type, "article": article}


def test_initial_state(v1: States) -> None:
    state = v1.at(0.0 - 1.0)
    assert state["time_s"] == 0.0
    assert state["occupied_cells"] == 9
    assert state["occupancy"] == pytest.approx(0.9)
    assert state["completed"] == 0
    assert state["cranes"]["1"]["position"] == [0.0, 0.0]
    assert state["cranes"]["1"]["activity"] == "handling"


@pytest.mark.parametrize(
    ("time_s", "activity"),
    [
        (5.0, "handling"),
        (10.0, "moving_loaded"),
        (16.9, "moving_loaded"),
        (17.0, "handling"),
        (27.0, "idle"),
        (29.9, "idle"),
        (30.0, "handling"),  # the retrieval's empty move has zero length, and is never current
        (40.0, "moving_loaded"),
        (47.0, "handling"),
        (57.0, "idle"),
    ],
)
def test_crane_activity(v1: States, time_s: float, activity: str) -> None:
    assert v1.at(time_s)["cranes"]["1"]["activity"] == activity


def test_crane_order(v1: States) -> None:
    assert v1.at(5.0)["cranes"]["1"]["order"] == 0
    assert v1.at(28.0)["cranes"]["1"]["order"] is None
    assert v1.at(35.0)["cranes"]["1"]["order"] == 1


@pytest.mark.parametrize(
    ("time_s", "carrying", "cell_state"),
    [
        (9.9, False, "reserved_for_storage"),
        (10.0, True, "reserved_for_storage"),
        (26.9, True, "reserved_for_storage"),
        (27.0, False, "occupied"),
        (30.0, False, "reserved_for_retrieval"),
        (39.9, False, "reserved_for_retrieval"),
        (40.0, True, "free"),
        (56.9, True, "free"),
        (57.0, False, "free"),
    ],
)
def test_load_unit_times_and_cell_states(
    v1: States, time_s: float, carrying: bool, cell_state: str
) -> None:
    assert (v1.at(time_s)["cranes"]["1"]["carrying"] is not None) == carrying
    assert v1.cell_at(time_s, CELL)["state"] == cell_state


def test_cell_before_any_order_is_free_and_has_no_load(modules: Modules, v1: States) -> None:
    states = States(modules, {**v1.data, "events": [], "orders": []})
    cell = states.cell_at(0.0, CELL)
    assert cell["state"] == "free"
    assert cell["load"] is None


@pytest.mark.parametrize(
    ("time_s", "article_expected"),
    [(9.9, False), (27.0, True), (35.0, True), (40.0, False)],
)
def test_only_occupied_and_retrieval_cells_hold_a_load_unit(
    v1: States, time_s: float, article_expected: bool
) -> None:
    stored = v1.stored_at(time_s)
    locations = [unit["location"] for unit in stored]
    assert (CELL in locations) == article_expected
    assert len(stored) == (10 if article_expected else 9)


def test_stored_load_unit_details(v1: States) -> None:
    stored = {tuple(unit["location"]): unit for unit in v1.stored_at(35.0)}
    new_unit = stored[tuple(CELL)]
    assert v1.data["articles"][new_unit["article"]] == "A"
    assert new_unit["store_order"] == 0
    assert new_unit["retrieve_order"] == 1
    initial = stored[(1, 1, 1, 1)]
    assert v1.data["articles"][initial["article"]] == "B"
    assert initial["store_order"] is None


def test_counts_at_the_end(v1: States) -> None:
    state = v1.at(3600.0)
    assert state["completed"] == 2
    assert state["arrived"] == 2
    assert state["unfulfillable"] == 0
    assert state["occupied_cells"] == 9
    assert state["backlog"] == {"total": 0, "per_aisle": {"1": 0}, "waiting_for_cell": 0}


def test_time_stays_within_the_run(v1: States) -> None:
    assert v1.at(-5.0)["time_s"] == 0.0
    assert v1.at(99999.0)["time_s"] == 3600.0


def test_warm_up_or_measurement_window(modules: Modules, write_run: Callable[..., Path]) -> None:
    verification = SAMPLES / "verification"
    states = States(
        modules,
        replay_data(
            write_run(verification / "v1-warehouse.yaml", verification / "v3-scenario.yaml")
        ),
    )
    assert states.at(19.9)["in_measurement_window"] is False
    assert states.at(20.0)["in_measurement_window"] is True


def test_run_with_no_orders(
    modules: Modules, write_run: Callable[..., Path], tmp_path: Path
) -> None:
    states = states_of(modules, write_run, tmp_path, stocked((3, 2)), [])
    for time_s in (0.0, 100.0, 3600.0):
        state = states.at(time_s)
        assert state["completed"] == state["arrived"] == 0
        assert state["occupied_cells"] == 9
        assert state["cranes"]["1"]["activity"] == "idle"
        assert state["cranes"]["1"]["position"] == [0.0, 0.0]


def test_unfinished_order_stops_at_the_end_of_the_run(
    modules: Modules, write_run: Callable[..., Path], tmp_path: Path
) -> None:
    # The loaded move from 10 s to 17 s is cut off at 12 s, when the crane is at (2, 1.5).
    states = states_of(
        modules, write_run, tmp_path, stocked((3, 2)), [order(0, "storage", "A")], duration_s=12
    )
    state = states.at(12.0)
    assert state["cranes"]["1"]["position"] == pytest.approx([2.0, 1.5])
    assert state["cranes"]["1"]["activity"] == "moving_loaded"
    assert state["cranes"]["1"]["carrying"] is not None
    assert state["completed"] == 0
    assert state["occupied_cells"] == 9


def test_unfulfillable_order_moves_nothing_and_is_counted(
    modules: Modules, write_run: Callable[..., Path], tmp_path: Path
) -> None:
    states = states_of(
        modules, write_run, tmp_path, stocked((3, 2)), [order(5, "retrieval", "MISSING")]
    )
    state = states.at(6.0)
    assert state["unfulfillable"] == 1
    assert state["arrived"] == 1
    assert state["backlog"]["total"] == 0
    assert state["cranes"]["1"]["activity"] == "idle"
    assert state["cranes"]["1"]["position"] == [0.0, 0.0]


def test_waiting_storage_order_counts_without_a_load_unit(
    modules: Modules, write_run: Callable[..., Path], tmp_path: Path
) -> None:
    states = states_of(modules, write_run, tmp_path, stocked(), [order(5, "storage", "A")])
    state = states.at(6.0)
    assert state["backlog"]["total"] == 1
    assert state["backlog"]["waiting_for_cell"] == 1
    assert state["backlog"]["per_aisle"] == {"1": 0}
    assert state["occupied_cells"] == 10
    assert state["cranes"]["1"]["carrying"] is None


def test_waiting_storage_order_stops_waiting_when_a_cell_is_released(
    modules: Modules, write_run: Callable[..., Path], tmp_path: Path
) -> None:
    # The retrieval picks up its load unit at 10 + 2·sqrt(2) + 10 s, which releases a cell.
    states = states_of(
        modules,
        write_run,
        tmp_path,
        stocked(),
        [order(0, "storage", "A"), order(10, "retrieval", "B")],
    )
    waiting = states.at(15.0)["backlog"]
    assert waiting == {"total": 1, "per_aisle": {"1": 0}, "waiting_for_cell": 1}
    queued = states.at(23.0)["backlog"]
    assert queued == {"total": 1, "per_aisle": {"1": 1}, "waiting_for_cell": 0}


def test_queued_order_counts_for_its_aisle_until_it_starts(
    modules: Modules, write_run: Callable[..., Path], tmp_path: Path
) -> None:
    states = states_of(
        modules,
        write_run,
        tmp_path,
        stocked((3, 2), (2, 2)),
        [order(0, "storage", "A"), order(1, "storage", "A")],
    )
    state = states.at(2.0)
    assert state["backlog"] == {"total": 1, "per_aisle": {"1": 1}, "waiting_for_cell": 0}
    first_completion = states.data["orders"][0][5]
    state = states.at(first_completion)
    assert state["backlog"]["total"] == 0


def test_order_started_on_arrival_is_not_backlog(v1: States) -> None:
    assert v1.at(0.0)["backlog"]["total"] == 0
    assert v1.at(30.0)["backlog"]["total"] == 0


def test_zero_handling_times_cause_no_gap(
    modules: Modules, write_run: Callable[..., Path], tmp_path: Path
) -> None:
    warehouse = stocked((3, 2))
    warehouse["crane"]["pick_time_s"] = 0
    warehouse["crane"]["set_time_s"] = 0
    states = states_of(modules, write_run, tmp_path, warehouse, [order(0, "storage", "A")])
    assert states.at(0.0)["cranes"]["1"]["activity"] == "moving_loaded"
    assert states.at(0.0)["cranes"]["1"]["carrying"] is not None
    assert states.at(3.5)["cranes"]["1"]["activity"] == "moving_loaded"
    final = states.at(7.0)
    assert final["cranes"]["1"]["activity"] == "idle"
    assert final["completed"] == 1
    assert final["occupied_cells"] == 10


def test_changed_cells_are_reported_for_drawing(v1: States) -> None:
    changes = v1.evaluate(
        "const changes = [];"
        "state.stateAt(26.0); state.takeChanges();"
        "state.stateAt(28.0); changes.push(state.takeChanges());"
        "state.stateAt(28.5); changes.push(state.takeChanges());"
        "state.stateAt(10.0); changes.push(state.takeChanges());"
        "return changes;"
    )
    assert changes[0] == {"all": False, "cells": [CELL]}
    assert changes[1] == {"all": False, "cells": []}
    assert changes[2]["all"] is True


def test_result_is_valid_json_with_no_shared_state(v1: States) -> None:
    first = v1.evaluate(
        "const a = state.stateAt(5.0); const copy = JSON.stringify(a);"
        "state.stateAt(50.0); return [copy, JSON.stringify(a)];"
    )
    assert first[0] == first[1]
    assert json.loads(first[0])["time_s"] == 5.0
