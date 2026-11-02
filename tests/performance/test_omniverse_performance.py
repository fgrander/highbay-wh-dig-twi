"""SC-003, SC-004, and SC-005, measured in Kit at 1920x1080 with the whole warehouse in view.

The frame limiter and eco mode are switched off, to measure capacity rather than a chosen limit.
"""

from pathlib import Path
from typing import Any

import pytest
from write_planning_target import write_planning_target

from conftest import SAMPLES
from highbay_sim.cli import main
from kit_runner import ROOT, run_kit_script

pytestmark = [pytest.mark.performance, pytest.mark.omniverse]

SCRIPT = ROOT / "tests" / "omniverse_kit" / "performance_script.py"
SETTINGS = [
    "--/app/viewport/defaults/fillViewport=false",
    "--/rtx/ecoMode/enabled=false",
    "--/app/vsync=false",
    "--/app/runLoops/main/rateLimitEnabled=false",
]
SMALL_MIN_FPS = 30.0
LARGE_MIN_FPS = 10.0
LARGE_MAX_OPEN_S = 300.0
MAX_MOVE_S = 1.0
LARGE_TIME_LIMIT_S = 900.0


def measure(folder: Path, work: Path, time_limit_s: float = 420.0) -> dict[str, Any]:
    found = run_kit_script(
        SCRIPT, {"run_folder": str(folder)}, work, settings=SETTINGS, time_limit_s=time_limit_s
    )
    assert "script_error" not in found, found.get("script_error")
    assert found["resolution"] == [1920, 1080]
    assert found["camera"] == "/World/Camera"
    print(
        f"open {found['open_s']:.1f} s, {found['playing']['fps']:.1f} fps, slowest frame "
        f"{found['playing']['slowest_frame_s'] * 1000:.0f} ms, "
        f"played to {found['played_to_s']:.0f} s, "
        f"slowest move {max(found['moves_s']):.3f} s"
    )
    return found


@pytest.fixture(scope="module")
def small(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    root = tmp_path_factory.mktemp("small")
    arguments = [
        "run",
        str(SAMPLES / "small-warehouse.yaml"),
        str(SAMPLES / "daily-scenario.yaml"),
        "--output",
        str(root / "run"),
        "--replay",
    ]
    assert main(arguments) == 0
    return measure(root / "run", root)


@pytest.fixture(scope="module")
def large(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    root = tmp_path_factory.mktemp("large")
    (root / "run").mkdir()
    write_planning_target(root / "run")
    return measure(root / "run", root, LARGE_TIME_LIMIT_S)


def test_small_warehouse_frame_rate(small: dict[str, Any]) -> None:
    assert small["playing"]["fps"] >= SMALL_MIN_FPS


def test_moving_to_any_time_on_the_small_warehouse(small: dict[str, Any]) -> None:
    assert max(small["moves_s"]) < MAX_MOVE_S


def test_planning_target_opens_in_time(large: dict[str, Any]) -> None:
    assert large["open_s"] < LARGE_MAX_OPEN_S


def test_planning_target_frame_rate(large: dict[str, Any]) -> None:
    assert large["playing"]["fps"] >= LARGE_MIN_FPS
