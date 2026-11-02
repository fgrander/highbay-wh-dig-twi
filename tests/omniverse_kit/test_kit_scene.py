"""The USD scene, checked inside Kit against the recording's state (FR-002, FR-005, FR-016)."""

import json
import random
from pathlib import Path
from typing import Any

import pytest

from conftest import SAMPLES
from highbay.replay.core.layout import create_layout
from highbay.replay.core.recorded_source import open_recording
from highbay_sim.cli import main
from kit_runner import run_kit_script

pytestmark = pytest.mark.omniverse

SCRIPT = Path(__file__).parent / "scene_script.py"
PLAY_END_S = 3600.0
TOLERANCE_M = 0.01


@pytest.fixture(scope="module")
def run_folder(tmp_path_factory: pytest.TempPathFactory) -> Path:
    folder = tmp_path_factory.mktemp("scene") / "run"
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


@pytest.fixture(scope="module")
def times(run_folder: Path) -> list[float]:
    generator = random.Random(1)
    duration = open_recording(run_folder).time_range()[1]
    return sorted(generator.uniform(0.0, duration) for _ in range(20))


@pytest.fixture(scope="module")
def results(
    run_folder: Path, times: list[float], tmp_path_factory: pytest.TempPathFactory
) -> dict[str, Any]:
    work = tmp_path_factory.mktemp("kit")
    empty = work / "empty"
    empty.mkdir()
    data = json.loads((run_folder / "replay.json").read_text(encoding="utf-8"))
    data["events"] = []
    data["orders"] = []
    (empty / "replay.json").write_text(json.dumps(data), encoding="utf-8")

    found = run_kit_script(
        SCRIPT,
        {
            "run_folder": str(run_folder),
            "empty_folder": str(empty),
            "times": times,
            "play_end_s": PLAY_END_S,
        },
        work,
    )
    assert "script_error" not in found, found.get("script_error")
    return found


def expected_scene(source: Any, time_s: float) -> dict[str, Any]:
    """Works out from the state interface alone what the scene must show at a time."""
    layout = create_layout(source.describe().layout)
    state = source.state_at(time_s)
    visible = {
        layout.cell_instance(load.location): load.article % 8 for load in source.stored_load_units()
    }
    return {
        "invisible": sorted(set(range(layout.cell_count)) - set(visible)),
        "visible": visible,
        "cranes": {
            f"Aisle_{aisle}": {
                "translate": [crane.position[0], 0.0, layout.aisle_center_z(aisle)],
                "carriage_y": crane.position[1],
                "carrying": crane.carrying is not None,
            }
            for aisle, crane in state.cranes.items()
        },
    }


def assert_scene_shows(snapshot: dict[str, Any], expected: dict[str, Any]) -> None:
    assert snapshot["invisible"] == expected["invisible"]
    for instance, prototype in expected["visible"].items():
        assert snapshot["prototypes"][instance] == prototype
    for name, crane in expected["cranes"].items():
        found = snapshot["cranes"][name]
        assert found["translate"] == pytest.approx(crane["translate"], abs=TOLERANCE_M)
        assert found["carriage"][1] == pytest.approx(crane["carriage_y"], abs=TOLERANCE_M)
        assert found["carried_visible"] == crane["carrying"]


def test_stage_units(results: dict[str, Any]) -> None:
    assert results["up_axis"] == "Y"
    assert results["meters_per_unit"] == 1.0


def test_prims_of_the_data_model_exist(results: dict[str, Any]) -> None:
    assert results["prims"] == {
        "/World/Floor": "Cube",
        "/World/Dome": "DomeLight",
        "/World/Sun": "DistantLight",
        "/World/Racks": "PointInstancer",
        "/World/Loads": "PointInstancer",
        "/World/Cranes/Aisle_1": "Xform",
        "/World/Cranes/Aisle_1/Carriage": "Xform",
        "/World/Camera": "Camera",
        "/World/Selection": "Xform",
    }


def test_transfer_points_follow_their_aisle_ends(results: dict[str, Any], run_folder: Path) -> None:
    description = open_recording(run_folder).describe()
    expected = [
        f"Aisle_{aisle}_{end}_{role}"
        for aisle in range(1, description.layout["aisle_count"] + 1)
        for end in ("left", "right")
        for role in ("inbound", "outbound")
        if role in description.transfer_points[str(aisle)][end]
    ]
    assert sorted(results["transfer_points"]) == sorted(expected)


def test_instances(results: dict[str, Any], run_folder: Path) -> None:
    layout = create_layout(open_recording(run_folder).describe().layout)
    assert results["load_instances"] == layout.cell_count
    assert results["load_prototypes"] == 8
    assert results["first_load_position"] == pytest.approx(
        list(layout.cell_box((1, 1, 1, 1)).center)
    )
    racks = layout.aisle_count * layout.racks_per_aisle
    assert results["rack_instances"] == racks * 2 * (layout.bays + 1 + layout.levels + 1)


def test_scene_at_the_start_shows_initial_stock(results: dict[str, Any], run_folder: Path) -> None:
    assert_scene_shows(results["start"], expected_scene(open_recording(run_folder), 0.0))


def test_scene_matches_the_state_at_sampled_times(
    results: dict[str, Any], run_folder: Path, times: list[float]
) -> None:
    source = open_recording(run_folder)
    for snapshot, time_s in zip(results["forward"], times, strict=True):
        assert_scene_shows(snapshot, expected_scene(source, time_s))


def test_moving_backward_gives_the_same_scene_as_moving_forward(results: dict[str, Any]) -> None:
    for forward, backward in zip(results["forward"], results["backward"], strict=True):
        assert forward["invisible"] == backward["invisible"]
        assert forward["cranes"] == backward["cranes"]


def test_two_builds_are_identical(results: dict[str, Any]) -> None:
    assert results["same_text"], "\n".join(results["text_diff"])


def test_recording_with_no_events_plays_to_its_end(
    results: dict[str, Any], run_folder: Path
) -> None:
    assert_scene_shows(results["empty"], expected_scene(open_recording(run_folder), 0.0))


def test_update_rate_has_no_effect_on_the_state(results: dict[str, Any], run_folder: Path) -> None:
    expected = expected_scene(open_recording(run_folder), PLAY_END_S)
    assert_scene_shows(results["rate_slow"], expected)
    assert_scene_shows(results["rate_fast"], expected)


def test_many_events_in_one_frame_all_take_effect(
    results: dict[str, Any], run_folder: Path
) -> None:
    expected = expected_scene(open_recording(run_folder), PLAY_END_S)
    assert_scene_shows(results["many_per_frame"], expected)
