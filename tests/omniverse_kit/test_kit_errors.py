"""FR-014, and the rule for opening a run while another one is open, checked inside Kit."""

import json
from pathlib import Path
from typing import Any

import pytest

from conftest import SAMPLES
from highbay_sim.cli import main
from kit_runner import run_kit_script

pytestmark = pytest.mark.omniverse

SCRIPT = Path(__file__).parent / "errors_script.py"
LATER_S = 500.0


def record(warehouse: Path, scenario: Path, folder: Path) -> Path:
    arguments = ["run", str(warehouse), str(scenario), "--output", str(folder), "--replay"]
    assert main(arguments) == 0
    return folder


@pytest.fixture(scope="module")
def folders(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    root = tmp_path_factory.mktemp("errors")
    good = record(SAMPLES / "small-warehouse.yaml", SAMPLES / "daily-scenario.yaml", root / "good")
    other = record(
        SAMPLES / "replay" / "overloaded-warehouse.yaml",
        SAMPLES / "replay" / "busy-scenario.yaml",
        root / "other",
    )
    missing = root / "missing"
    missing.mkdir()
    damaged = root / "damaged"
    damaged.mkdir()
    (damaged / "replay.json").write_text("{not json", encoding="utf-8")
    unsupported = root / "unsupported"
    unsupported.mkdir()
    data = json.loads((good / "replay.json").read_text(encoding="utf-8"))
    (unsupported / "replay.json").write_text(
        json.dumps({**data, "format_version": 999}), encoding="utf-8"
    )
    return {
        "good": good,
        "other": other,
        "missing": missing,
        "damaged": damaged,
        "unsupported": unsupported,
    }


@pytest.fixture(scope="module")
def results(folders: dict[str, Path], tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    found = run_kit_script(
        SCRIPT,
        {
            "good_folder": str(folders["good"]),
            "other_folder": str(folders["other"]),
            "bad_folders": {
                name: str(folders[name]) for name in ("missing", "damaged", "unsupported")
            },
            "later_s": LATER_S,
        },
        tmp_path_factory.mktemp("kit"),
    )
    assert "script_error" not in found, found.get("script_error")
    return found


@pytest.mark.parametrize(
    ("name", "problem"),
    [
        ("missing", "no recording"),
        ("damaged", "damaged"),
        ("unsupported", "format version 999"),
    ],
)
def test_bad_folder_names_the_file_and_problem_and_opens_no_scene(
    results: dict[str, Any], name: str, problem: str
) -> None:
    assert "replay.json" in results[name]["message"]
    assert problem in results[name]["message"]
    assert not results[name]["has_scene"]


def test_unsupported_version_names_both_versions(results: dict[str, Any]) -> None:
    assert "version 1" in results["unsupported"]["message"]


def test_good_folder_opens_and_clears_the_message(results: dict[str, Any]) -> None:
    assert results["opened"]["message"] == ""
    assert results["opened"]["has_scene"]
    assert results["opened"]["time_s"] == LATER_S


def test_bad_folder_leaves_an_open_run_unchanged(results: dict[str, Any]) -> None:
    kept = results["kept"]
    assert "format version 999" in kept["message"]
    assert kept["same_source"]
    assert kept["time_s"] == LATER_S
    assert kept["has_scene"]


def test_good_folder_replaces_an_open_run_paused_at_the_start(results: dict[str, Any]) -> None:
    replaced = results["replaced"]
    assert replaced["message"] == ""
    assert not replaced["same_source"]
    assert replaced["time_s"] == 0.0
    assert not replaced["playing"]
