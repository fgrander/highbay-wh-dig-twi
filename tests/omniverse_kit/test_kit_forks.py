"""Forks and pairs during handling, checked inside Kit (FR-006 to FR-009, SC-002)."""

import json
from pathlib import Path
from typing import Any

import pytest

from conftest import SAMPLES
from highbay.replay.core.crane_dimensions import crane_dimensions
from highbay.replay.core.layout import create_layout
from highbay.replay.core.recorded_source import open_recording
from highbay_sim.cli import main
from kit_runner import run_kit_script

pytestmark = pytest.mark.omniverse

SCRIPT = Path(__file__).parent / "forks_script.py"
DATA = Path(__file__).parents[1] / "data"
LOOK = DATA / "look_crane_mast.usda"
SHARES = (0.0, 0.2, 0.5, 0.8, 0.999)
TOLERANCE_M = 0.01
_TIME, _KIND, _CRANE, _LOCATION = 0, 1, 3, 4


@pytest.fixture(scope="module")
def run_folder(tmp_path_factory: pytest.TempPathFactory) -> Path:
    folder = tmp_path_factory.mktemp("forks") / "run"
    arguments = [
        "run",
        str(SAMPLES / "small-warehouse.yaml"),
        str(SAMPLES / "daily-scenario.yaml"),
        "--output",
        str(folder),
        "--replay",
    ]
    assert main(arguments) == 0
    return folder


def find_steps(run_folder: Path) -> list[dict[str, Any]]:
    """Returns one pick and one set at a cell in each rack, in the order of the recording."""
    data = json.loads((run_folder / "replay.json").read_text(encoding="utf-8"))
    source = open_recording(run_folder)
    layout = create_layout(source.describe().layout)
    size = crane_dimensions(layout)
    steps: dict[tuple[str, int], dict[str, Any]] = {}
    for row in data["events"]:
        if row[_KIND] not in ("load_picked", "load_set") or row[_LOCATION] is None:
            continue
        kind = "pick" if row[_KIND] == "load_picked" else "set"
        location = row[_LOCATION]
        if (kind, location[1]) in steps:
            continue
        handling = source.state_at(row[_TIME] - 0.001).cranes[row[_CRANE]].handling
        assert handling is not None
        start, end = handling.start_s, handling.end_s
        times = [start + share * (end - start) for share in SHARES]
        reach = layout.rack_z(location[0], location[1]) - layout.aisle_center_z(location[0])
        crane_x = source.state_at(start).cranes[row[_CRANE]].position[0]
        steps[(kind, location[1])] = {
            "kind": kind,
            "aisle": row[_CRANE],
            "location": location,
            "instance": layout.cell_instance(tuple(location)),
            "times": times,
            "after": end + 1.0,
            "middle": start + 0.5 * (end - start),
            "reach": reach,
            # On section 1 and over the rack's front, where only an extended fork can be.
            "fork_click": [
                crane_x - size.section_x,
                layout.aisle_center_z(row[_CRANE]) + reach * 0.9,
            ],
        }
    assert len(steps) == 4
    return list(steps.values())


@pytest.fixture(scope="module")
def results(run_folder: Path, tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    found = run_kit_script(
        SCRIPT,
        {
            "run_folder": str(run_folder),
            "steps": find_steps(run_folder),
            "scripted_data": str(DATA),
        },
        tmp_path_factory.mktemp("kit"),
        models="detailed",
    )
    assert "script_error" not in found, found.get("script_error")
    return found


@pytest.mark.parametrize(
    ("share", "extension"),
    [(0.0, 0.0), (0.2, 0.5), (0.5, 1.0), (0.8, 0.5), (0.999, 0.0)],
)
def test_all_stages_of_both_sections_follow_the_time(
    results: dict[str, Any], share: float, extension: float
) -> None:
    index = SHARES.index(share)
    for step in results["steps"]:
        shown = step["forward"][str(step["times"][index])]["stages"]
        distance = step["reach"] * extension
        for section in ("Section1", "Section2"):
            assert shown[f"{section}/Top"][2] == pytest.approx(distance, abs=TOLERANCE_M)
            assert shown[f"{section}/Middle"][2] == pytest.approx(distance / 2, abs=TOLERANCE_M)


def test_a_picked_pair_leaves_its_cell_and_returns_on_the_forks(results: dict[str, Any]) -> None:
    for step in results["steps"]:
        if step["kind"] != "pick":
            continue
        for time_s, share in zip(step["times"], SHARES, strict=True):
            shown = step["forward"][str(time_s)]
            expected = step["reach"] * (1.0 if share <= 0.6 else (1.0 - share) / 0.4)
            assert shown["carried_visible"]
            assert shown["carried_position"][2] == pytest.approx(expected, abs=TOLERANCE_M)
            assert step["instance"] in shown["hidden"]


def test_a_set_pair_goes_out_and_stays_at_its_cell(results: dict[str, Any]) -> None:
    for step in results["steps"]:
        if step["kind"] != "set":
            continue
        for time_s, share in zip(step["times"], SHARES, strict=True):
            shown = step["forward"][str(time_s)]
            expected = step["reach"] * (share / 0.4 if share < 0.4 else 1.0)
            assert shown["carried_visible"]
            assert shown["carried_position"][2] == pytest.approx(expected, abs=TOLERANCE_M)
            # The recording stores it at the end of the step.
            assert step["instance"] in shown["hidden"]


def test_each_time_looks_the_same_reached_forward_or_backward(results: dict[str, Any]) -> None:
    for step in results["steps"]:
        for time_s in step["times"]:
            assert step["forward"][str(time_s)] == step["backward"][str(time_s)], time_s


def test_a_click_on_extended_forks_selects_the_crane(results: dict[str, Any]) -> None:
    for step in results["steps"]:
        assert step["clicked"] == ["crane", step["aisle"]], step["location"]


def test_forks_rest_for_a_source_with_no_handling(results: dict[str, Any]) -> None:
    for name, position in results["scripted"]["stages"].items():
        assert position == [0.0, 0.0, 0.0], name


def test_nothing_is_reported_as_a_problem(results: dict[str, Any]) -> None:
    assert results["message"] == ""


def test_a_carriage_file_with_no_stages_does_not_stop_a_run(
    run_folder: Path, tmp_path: Path
) -> None:
    script = Path(__file__).parent / "looks_script.py"
    found = run_kit_script(
        script,
        {
            "run_folder": str(run_folder),
            "times": [step["middle"] for step in find_steps(run_folder)],
        },
        tmp_path,
        settings=[f"--/exts/highbay.replay/looks/crane_carriage={LOOK}"],
        models="detailed",
    )
    assert "script_error" not in found, found.get("script_error")
    assert found["message"] == ""
