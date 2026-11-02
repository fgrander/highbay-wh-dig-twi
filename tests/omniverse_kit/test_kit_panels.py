"""Figures, details, and the jump to the highest backlog, checked inside Kit (User Story 2)."""

import random
from pathlib import Path
from typing import Any

import pytest

from conftest import SAMPLES
from highbay.replay.core.display_text import figure_lines, run_identification
from highbay.replay.core.recorded_source import open_recording
from highbay_sim.cli import main
from kit_runner import run_kit_script

pytestmark = pytest.mark.omniverse

SCRIPT = Path(__file__).parent / "panels_script.py"


@pytest.fixture(scope="module")
def run_folder(tmp_path_factory: pytest.TempPathFactory) -> Path:
    folder = tmp_path_factory.mktemp("panels") / "run"
    arguments = [
        "run",
        str(SAMPLES / "replay" / "overloaded-warehouse.yaml"),
        str(SAMPLES / "replay" / "busy-scenario.yaml"),
        "--output",
        str(folder),
        "--replay",
    ]
    assert main(arguments) == 0
    return folder


@pytest.fixture(scope="module")
def times(run_folder: Path) -> list[float]:
    generator = random.Random(1)
    duration = open_recording(run_folder).time_range()[1]
    return sorted(generator.uniform(0.0, duration) for _ in range(10))


@pytest.fixture(scope="module")
def results(
    run_folder: Path, times: list[float], tmp_path_factory: pytest.TempPathFactory
) -> dict[str, Any]:
    found = run_kit_script(
        SCRIPT,
        {"run_folder": str(run_folder), "times": times},
        tmp_path_factory.mktemp("kit"),
    )
    assert "script_error" not in found, found.get("script_error")
    return found


def test_figures_match_the_state_at_sampled_times(
    results: dict[str, Any], run_folder: Path, times: list[float]
) -> None:
    source = open_recording(run_folder)
    for shown, time_s in zip(results["at_times"], times, strict=True):
        assert shown["figures"] == figure_lines(source.state_at(time_s))


def test_crane_colors_follow_the_activity(
    results: dict[str, Any], run_folder: Path, times: list[float]
) -> None:
    source = open_recording(run_folder)
    colors: dict[str, list[float]] = {}
    for shown, time_s in zip(results["at_times"], times, strict=True):
        for aisle, crane in source.state_at(time_s).cranes.items():
            known = colors.setdefault(crane.activity, shown["colors"][str(aisle)])
            assert shown["colors"][str(aisle)] == known
    assert len({tuple(color) for color in colors.values()}) == len(colors)


def test_run_identification_and_legend(results: dict[str, Any], run_folder: Path) -> None:
    description = open_recording(run_folder).describe()
    assert results["identification"] == run_identification(description)
    assert results["legend"] == [
        *description.articles,
        "Moving empty",
        "Moving loaded",
        "Handling",
        "Idle",
    ]


def test_jump_to_the_highest_backlog(results: dict[str, Any], run_folder: Path) -> None:
    reported = open_recording(run_folder).describe().reported
    assert reported is not None
    peak = results["peak"]
    assert not peak["playing"]
    assert peak["time_s"] == reported["first_backlog_peak_s"]
    assert peak["figures"][1] == f"Backlog: {reported['backlog_orders']['max_in_window']}"


def test_selecting_a_crane_shows_its_details_and_outline(results: dict[str, Any]) -> None:
    selected = results["crane_selected"]
    assert selected["details"][0] == "Crane 1"
    assert selected["highlight"]["visibility"] != "invisible"


def test_click_position_finds_what_is_shown_there(results: dict[str, Any]) -> None:
    assert results["clicked"]["details"][0] == "Crane 1"


def test_kit_does_not_select_objects_in_the_viewport(results: dict[str, Any]) -> None:
    assert results["kit_selection"] is False


def test_selecting_nothing_clears_details_and_outline(results: dict[str, Any]) -> None:
    cleared = results["nothing_selected"]
    assert cleared["details"] == []
    assert cleared["highlight"]["visibility"] == "invisible"
