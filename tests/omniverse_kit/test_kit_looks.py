"""FR-013: a look can be replaced through a setting, with no change to positions or behavior."""

from pathlib import Path
from typing import Any

import pytest

from conftest import SAMPLES
from highbay.replay.core.layout import create_layout
from highbay.replay.core.recorded_source import open_recording
from highbay_sim.cli import main
from kit_runner import run_kit_script

pytestmark = pytest.mark.omniverse

SCRIPT = Path(__file__).parent / "looks_script.py"
LOOK = Path(__file__).parents[1] / "data" / "look_crane_mast.usda"
TIMES = [0.0, 2750.0, 3000.0, 3300.0]


@pytest.fixture(scope="module")
def run_folder(tmp_path_factory: pytest.TempPathFactory) -> Path:
    folder = tmp_path_factory.mktemp("looks") / "run"
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
def results(run_folder: Path, tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    found = run_kit_script(
        SCRIPT,
        {"run_folder": str(run_folder), "times": TIMES},
        tmp_path_factory.mktemp("kit"),
        settings=[
            f"--/exts/highbay.replay/looks/crane_mast={LOOK}",
            "--/exts/highbay.replay/looks/rack_beam=does-not-exist.usda",
        ],
    )
    assert "script_error" not in found, found.get("script_error")
    return found


def test_replacement_is_referenced_in_place_of_the_simple_shape(results: dict[str, Any]) -> None:
    assert results["mast_type"] == "Xform"
    assert results["mast_has_reference"]
    assert results["mast_child"] == "Sphere"


def test_replacement_stands_where_the_simple_shape_stood(
    results: dict[str, Any], run_folder: Path
) -> None:
    layout = create_layout(open_recording(run_folder).describe().layout)
    assert results["mast_translate"] == pytest.approx([0.0, layout.height / 2, 0.0])


def test_crane_positions_do_not_change(results: dict[str, Any], run_folder: Path) -> None:
    source = open_recording(run_folder)
    layout = create_layout(source.describe().layout)
    for time_s in TIMES:
        x, _ = source.state_at(time_s).cranes[1].position
        assert results["positions"][str(time_s)] == pytest.approx(
            [x, 0.0, layout.aisle_center_z(1)], abs=0.01
        )


def test_activity_colors_still_reach_a_replaced_look(results: dict[str, Any]) -> None:
    assert len({tuple(color) for color in results["colors"].values()}) > 1


def test_missing_file_gives_the_simple_shape_and_a_warning_naming_the_type(
    results: dict[str, Any],
) -> None:
    assert results["beam_type"] == "Cube"
    assert any("rack_beam" in warning for warning in results["warnings"])
    assert not any("crane_mast" in warning for warning in results["warnings"])
    assert results["message"] == ""
