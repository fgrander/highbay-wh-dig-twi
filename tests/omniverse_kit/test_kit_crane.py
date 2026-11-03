"""The detailed crane, checked inside Kit (FR-001 to FR-005, FR-014, SC-001, SC-003)."""

import random
from pathlib import Path
from typing import Any

import pytest

from conftest import SAMPLES
from highbay.replay.core.recorded_source import open_recording
from highbay_sim.cli import main
from kit_runner import run_kit_script

pytestmark = pytest.mark.omniverse

SCRIPT = Path(__file__).parent / "crane_script.py"
TOLERANCE_M = 0.01
PLAY_END_S = 3600.0
SAMPLED_TIMES = 100
LOOK = Path(__file__).parents[1] / "data" / "look_crane_mast.usda"


def record(root: Path, name: str, *options: str) -> Path:
    arguments = [
        "run",
        str(SAMPLES / "small-warehouse.yaml"),
        str(SAMPLES / "daily-scenario.yaml"),
        "--output",
        str(root / name),
        "--replay",
        *options,
    ]
    assert main(arguments) == 0
    return root / name


@pytest.fixture(scope="module")
def run_folders(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    root = tmp_path_factory.mktemp("crane")
    return {"event": record(root, "event"), "stepped": record(root, "stepped", "--time-stepped")}


@pytest.fixture(scope="module")
def times() -> list[float]:
    generator = random.Random(1)
    return sorted(generator.uniform(0.0, PLAY_END_S) for _ in range(SAMPLED_TIMES))


def find_times(source: Any) -> tuple[float, dict[str, float]]:
    """Returns a time with crane 1 raised and empty, and one time for each of its activities."""
    raised = None
    activities: dict[str, float] = {}
    for candidate in range(int(source.time_range()[1])):
        crane = source.state_at(float(candidate)).cranes[1]
        activities.setdefault(crane.activity, float(candidate))
        if raised is None and crane.carrying is None and crane.position[1] > 1.0:
            raised = float(candidate)
    assert raised is not None
    assert len(activities) == 4
    return raised, activities


@pytest.fixture(scope="module")
def results(
    run_folders: dict[str, Path], times: list[float], tmp_path_factory: pytest.TempPathFactory
) -> dict[str, Any]:
    raised, activities = find_times(open_recording(run_folders["event"]))
    found = run_kit_script(
        SCRIPT,
        {
            "run_folders": {label: str(folder) for label, folder in run_folders.items()},
            "times": times,
            "raised_time": raised,
            "activity_times": activities,
        },
        tmp_path_factory.mktemp("kit"),
        models="detailed",
    )
    assert "script_error" not in found, found.get("script_error")
    return found


@pytest.mark.parametrize("mode", ["event", "stepped"])
def test_crane_follows_the_recording(
    results: dict[str, Any], run_folders: dict[str, Path], times: list[float], mode: str
) -> None:
    source = open_recording(run_folders[mode])
    for time_s in times:
        shown = results["runs"][mode][str(time_s)]
        recorded = source.state_at(time_s).cranes[1].position
        assert shown == pytest.approx(list(recorded), abs=TOLERANCE_M)


def test_scene_has_no_trace_of_a_temporary_layer(results: dict[str, Any]) -> None:
    assert not results["root_layer_has_temporary_layer"]
    assert results["two_builds_identical"]


def test_materials_arrive_at_their_new_paths(results: dict[str, Any]) -> None:
    assert results["bogie_material"] == "/World/Cranes/Aisle_1/Mast/Materials/CraneBlue"
    assert results["fork_material"].startswith("/World/Cranes/Aisle_1/Carriage/Platform/Materials/")


def test_each_aisle_has_a_light(results: dict[str, Any]) -> None:
    assert results["lights"] == ["RectLight"] * results["aisle_count"]


def test_selection_boxes_match_the_shown_parts(results: dict[str, Any]) -> None:
    assert results["boxes"].keys() == results["bounds"].keys()
    for name, box in results["boxes"].items():
        for bound in ("min", "max"):
            assert results["bounds"][name][bound] == pytest.approx(box[bound], abs=TOLERANCE_M), (
                name,
                bound,
            )


def test_clicks_on_each_part_select_the_crane(results: dict[str, Any]) -> None:
    assert len(results["clicks"]) >= 20
    for name, selection in results["clicks"].items():
        assert selection == ["crane", 1], name


def test_outline_of_a_crane_surrounds_its_load_space(results: dict[str, Any]) -> None:
    x, y = results["position"]
    expected = [x, y + results["cell_height"] / 2, results["crane_z"]]
    assert results["outline"] == pytest.approx(expected, abs=TOLERANCE_M)


def test_parts_without_a_material_show_the_activity(results: dict[str, Any]) -> None:
    colors = {tuple(load[0]) for load in results["colors"].values()}
    assert len(colors) == 4
    for load in results["colors"].values():
        assert load[0] == load[1]


def test_no_warnings_with_generated_models(results: dict[str, Any]) -> None:
    assert results["warnings"] == []
    assert results["message"] == ""


def test_a_file_replaces_a_generated_part_with_a_warning(
    run_folders: dict[str, Path], tmp_path: Path
) -> None:
    script = Path(__file__).parent / "looks_script.py"
    found = run_kit_script(
        script,
        {"run_folder": str(run_folders["event"]), "times": [0.0]},
        tmp_path,
        settings=[f"--/exts/highbay.replay/looks/crane_mast={LOOK}"],
        models="detailed",
    )
    assert "script_error" not in found, found.get("script_error")
    assert found["mast_has_reference"]
    assert any("crane_mast" in warning for warning in found["warnings"])
