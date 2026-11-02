"""SC-005 and SC-006: the state depends only on time, and ends as the report says."""

import random
from collections.abc import Callable
from pathlib import Path

from conftest import SAMPLES, Modules, replay_data

SNAPSHOT = (
    "const snapshot = (state, time) => JSON.stringify("
    "[state.stateAt(time), state.storedLoadUnits()]);"
)


def test_same_state_however_a_time_is_reached(
    modules: Modules, write_run: Callable[..., Path]
) -> None:
    data = replay_data(write_run(SAMPLES / "small-warehouse.yaml", SAMPLES / "daily-scenario.yaml"))
    generator = random.Random(1)
    times = sorted(generator.uniform(0.0, data["run"]["duration_s"]) for _ in range(200))
    event_times = [row[0] for row in data["events"]]
    times += [generator.choice(event_times) for _ in range(50)]
    times.sort()

    differences = modules.run(
        "const { createReplayState } = await imports('replay-state.js');"
        f"{SNAPSHOT}"
        "const [data, times] = args;"
        "const forward = createReplayState(data);"
        "const backward = createReplayState(data);"
        "const differences = [];"
        "const expected = times.map((time) => snapshot(createReplayState(data), time));"
        "times.forEach((time, index) => {"
        "  if (snapshot(forward, time) !== expected[index]) differences.push(['forward', time]);"
        "});"
        "[...times].reverse().forEach((time, index) => {"
        "  const expectedIndex = times.length - 1 - index;"
        "  if (snapshot(backward, time) !== expected[expectedIndex]) {"
        "    differences.push(['backward', time]);"
        "  }"
        "});"
        "return differences;",
        data,
        times,
    )
    assert differences == []


def test_end_of_run_figures_equal_the_report(
    modules: Modules, write_run: Callable[..., Path]
) -> None:
    data = replay_data(write_run(SAMPLES / "small-warehouse.yaml", SAMPLES / "daily-scenario.yaml"))
    state = modules.run(
        "const { createReplayState } = await imports('replay-state.js');"
        "return createReplayState(args[0]).stateAt(args[0].run.duration_s);",
        data,
    )
    reported = data["reported"]
    outcomes = reported["order_outcomes"]
    assert state["completed"] == outcomes["completed"]
    assert state["arrived"] == outcomes["generated"]
    assert state["unfulfillable"] == outcomes["unfulfillable"]
    assert state["backlog"]["total"] == reported["backlog_orders"]["at_window_end"]
    assert round(state["occupancy"], 6) == reported["storage_occupancy"]["at_window_end"]
    assert (
        sum(state["backlog"]["per_aisle"].values()) + state["backlog"]["waiting_for_cell"]
        == (state["backlog"]["total"])
    )


def test_backlog_parts_always_add_up(modules: Modules, write_run: Callable[..., Path]) -> None:
    data = replay_data(write_run(SAMPLES / "small-warehouse.yaml", SAMPLES / "daily-scenario.yaml"))
    mismatches = modules.run(
        "const { createReplayState } = await imports('replay-state.js');"
        "const state = createReplayState(args[0]);"
        "const mismatches = [];"
        "for (const row of args[0].events) {"
        "  const { backlog } = state.stateAt(row[0]);"
        "  const sum = Object.values(backlog.per_aisle).reduce((a, b) => a + b, 0);"
        "  if (sum + backlog.waiting_for_cell !== backlog.total) mismatches.push(row[0]);"
        "}"
        "return mismatches;",
        data,
    )
    assert mismatches == []
