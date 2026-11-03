"""SC-007: a source written only from the interface drives the scene and window, unchanged."""

import ast
from pathlib import Path
from typing import Any

import pytest

from kit_runner import ROOT, run_kit_script

pytestmark = pytest.mark.omniverse

SCRIPT = Path(__file__).parent / "state_source_script.py"
DATA = Path(__file__).parents[1] / "data"
REPLAY = ROOT / "omniverse" / "exts" / "highbay.replay" / "highbay" / "replay"
CELLS = 16


@pytest.fixture(scope="module")
def results(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    found = run_kit_script(SCRIPT, {"data_directory": str(DATA)}, tmp_path_factory.mktemp("kit"))
    assert "script_error" not in found, found.get("script_error")
    return found


def test_scripted_source_builds_and_shows_its_state(results: dict[str, Any]) -> None:
    start = results["start"]
    assert start["message"] == ""
    assert start["time_s"] == 0.0
    assert start["crane_x"] == 0.0
    assert start["hidden"] == CELLS - 1
    assert start["figures"][1] == "Backlog: 0"


def test_controls_that_need_moving_backward_are_disabled(results: dict[str, Any]) -> None:
    controls = results["controls"]
    assert controls["play"] is True
    assert controls["slider"] is False
    assert controls["restart"] is False
    assert controls["peak_visible"] is False


def test_no_run_identification_without_a_recording(results: dict[str, Any]) -> None:
    assert results["identification"] == []


def test_playback_holds_at_the_end_of_a_growing_range(results: dict[str, Any]) -> None:
    held = results["held"]
    assert held["time_s"] == 10.0
    assert held["playing"] is True
    assert held["crane_x"] == pytest.approx(1.0)


def test_playback_continues_when_the_range_grows(results: dict[str, Any]) -> None:
    continued = results["continued"]
    assert continued["time_s"] == 20.0
    assert continued["playing"] is True
    assert continued["crane_x"] == pytest.approx(2.0)
    assert continued["message"] == ""


def test_changes_from_the_source_reach_the_scene(results: dict[str, Any]) -> None:
    assert results["load_left"]["hidden"] == CELLS


def test_jump_to_the_highest_backlog_does_nothing_without_reported_values(
    results: dict[str, Any],
) -> None:
    assert results["no_jump"] is True


@pytest.mark.parametrize("module", ["scene.py", "window.py", "appearance.py"])
def test_display_code_does_not_know_about_recordings(module: str) -> None:
    tree = ast.parse((REPLAY / module).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert "recorded_source" not in node.module, module
            assert "recording" not in node.module, module
