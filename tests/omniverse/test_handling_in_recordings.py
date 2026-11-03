"""The facts about handling steps that the forks rely on, in recordings of both modes."""

import json
from pathlib import Path
from typing import Any

import pytest

from conftest import SAMPLES
from highbay_sim.cli import main

_TIME, _KIND, _CRANE, _LOCATION, _ACTIVITY, _END, _TARGET = 0, 1, 3, 4, 5, 6, 8
TOLERANCE_S = 1e-9
TOLERANCE_M = 1e-6


@pytest.fixture(scope="module", params=[[], ["--time-stepped"]], ids=["event", "stepped"])
def recording(
    request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory
) -> dict[str, Any]:
    folder: Path = tmp_path_factory.mktemp("handling") / "run"
    arguments = [
        "run",
        str(SAMPLES / "small-warehouse.yaml"),
        str(SAMPLES / "daily-scenario.yaml"),
        "--output",
        str(folder),
        "--replay",
        *request.param,
    ]
    assert main(arguments) == 0
    content: dict[str, Any] = json.loads((folder / "replay.json").read_text(encoding="utf-8"))
    return content


def test_pick_and_set_events_end_their_handling_steps(recording: dict[str, Any]) -> None:
    handling = {}
    seen = 0
    for row in recording["events"]:
        if row[_KIND] == "activity_started" and row[_ACTIVITY] == "handling":
            handling[row[_CRANE]] = row
        elif row[_KIND] in ("load_picked", "load_set"):
            seen += 1
            assert row[_TIME] == pytest.approx(handling[row[_CRANE]][_END], abs=TOLERANCE_S)
    assert seen > 0


def test_cranes_stand_at_the_floor_of_a_cell_when_handling(recording: dict[str, Any]) -> None:
    cell = recording["warehouse"]["layout"]["cell"]
    target = {}
    seen = 0
    for row in recording["events"]:
        if row[_KIND] == "activity_started" and row[_TARGET] is not None:
            target[row[_CRANE]] = row[_TARGET]
        elif row[_KIND] in ("load_picked", "load_set") and row[_LOCATION] is not None:
            seen += 1
            _aisle, _rack, bay, level = row[_LOCATION]
            assert target[row[_CRANE]][0] == pytest.approx(
                (bay - 0.5) * cell["length_m"], abs=TOLERANCE_M
            )
            assert target[row[_CRANE]][1] == pytest.approx(
                (level - 1) * cell["height_m"], abs=TOLERANCE_M
            )
    assert seen > 0
