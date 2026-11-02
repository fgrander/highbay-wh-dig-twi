"""SC-002: the Omniverse replay's logic gives the same results as the browser viewer's."""

import random
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest

from conftest import SAMPLES, Modules, replay_data
from highbay.replay.core.layout import create_layout
from highbay.replay.core.recorded_source import RecordedSource
from highbay_sim.cli import main

TOLERANCE_M = 0.01
SAMPLE_COUNT = 100


def sampled_times(data: dict[str, Any]) -> list[float]:
    generator = random.Random(1)
    duration = data["run"]["duration_s"]
    event_times = [row[0] for row in data["events"]]
    times = [generator.uniform(0.0, duration) for _ in range(SAMPLE_COUNT // 2)]
    times += [generator.choice(event_times) for _ in range(SAMPLE_COUNT - len(times))]
    return times


def browser_states(modules: Modules, data: dict[str, Any], times: list[float]) -> Any:
    return modules.run(
        "const { createReplayState } = await imports('replay-state.js');"
        "const [data, times] = args;"
        "const state = createReplayState(data);"
        "return times.map((time) => "
        "[state.stateAt(time), state.storedLoadUnits()]);",
        data,
        times,
    )


def assert_same_state(browser: dict[str, Any], stored: list[Any], source: RecordedSource) -> None:
    state = source.state_at(browser["time_s"])
    assert state.time_s == browser["time_s"]
    assert state.in_measurement_window == browser["in_measurement_window"]
    assert state.occupied_cells == browser["occupied_cells"]
    assert state.occupancy == browser["occupancy"]
    assert state.completed == browser["completed"]
    assert state.arrived == browser["arrived"]
    assert state.unfulfillable == browser["unfulfillable"]
    assert state.backlog.total == browser["backlog"]["total"]
    assert state.backlog.waiting_for_cell == browser["backlog"]["waiting_for_cell"]
    assert {str(key): value for key, value in state.backlog.per_aisle.items()} == browser[
        "backlog"
    ]["per_aisle"]

    for aisle, crane in state.cranes.items():
        expected = browser["cranes"][str(aisle)]
        assert crane.activity == expected["activity"]
        assert crane.order == expected["order"]
        assert crane.carrying == expected["carrying"]
        assert crane.position[0] == pytest.approx(expected["position"][0], abs=TOLERANCE_M)
        assert crane.position[1] == pytest.approx(expected["position"][1], abs=TOLERANCE_M)
        target = expected["movement_target"]
        assert crane.movement_target == (tuple(target) if target else None)

    loads = [asdict(load) for load in source.stored_load_units()]
    for load in loads:
        load["location"] = list(load["location"])
    assert loads == stored


@pytest.mark.parametrize("mode", ["event_based", "time_stepped"])
def test_state_matches_the_browser_at_sampled_times(
    modules: Modules, tmp_path: Path, mode: str
) -> None:
    arguments = [
        "run",
        str(SAMPLES / "small-warehouse.yaml"),
        str(SAMPLES / "daily-scenario.yaml"),
        "--output",
        str(tmp_path / "run"),
        "--replay",
    ]
    if mode == "time_stepped":
        arguments.append("--time-stepped")
    assert main(arguments) == 0
    data = replay_data(tmp_path / "run")
    times = sampled_times(data)

    results = browser_states(modules, data, times)
    source = RecordedSource(data)
    assert len(results) == SAMPLE_COUNT
    for state, stored in results:
        assert_same_state(state, stored, source)


def test_layout_matches_the_browser(modules: Modules, write_run: Callable[..., Path]) -> None:
    data = replay_data(write_run(SAMPLES / "small-warehouse.yaml", SAMPLES / "daily-scenario.yaml"))
    definition = data["warehouse"]["layout"]
    layout = create_layout(definition)
    locations = [
        [1, 1, 1, 1],
        [definition["aisle_count"], definition["racks_per_aisle"], 3, 2],
        [
            definition["aisle_count"],
            1,
            definition["bays_per_rack"],
            definition["levels_per_rack"],
        ],
    ]

    expected = modules.run(
        "const { createLayout } = await imports('layout.js');"
        "const [definition, locations] = args;"
        "const layout = createLayout(definition);"
        "return {"
        "  length: layout.length, height: layout.height, cellCount: layout.cellCount,"
        "  bounds: layout.bounds(),"
        "  boxes: locations.map((location) => layout.cellBox(location)),"
        "  left: layout.endX('left'), right: layout.endX('right'),"
        "  crane: layout.craneWorldPosition(definition.aisle_count, [2.5, 1.5]),"
        "};",
        definition,
        locations,
    )

    assert layout.length == expected["length"]
    assert layout.height == expected["height"]
    assert layout.cell_count == expected["cellCount"]
    assert list(layout.bounds().min) == pytest.approx(expected["bounds"]["min"])
    assert list(layout.bounds().max) == pytest.approx(expected["bounds"]["max"])
    assert layout.end_x("left") == expected["left"]
    assert layout.end_x("right") == expected["right"]
    world = layout.crane_world_position(definition["aisle_count"], (2.5, 1.5))
    assert list(world) == pytest.approx(expected["crane"])
    for location, box in zip(locations, expected["boxes"], strict=True):
        actual = layout.cell_box(tuple(location))
        assert list(actual.center) == pytest.approx(box["center"])
        assert list(actual.size) == pytest.approx(box["size"])
