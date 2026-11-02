"""A time-stepped run in the existing 3D replay (SC-006)."""

import csv
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from playwright.sync_api import Page

from conftest import SAMPLES
from highbay_sim.cli import main

VERIFICATION = SAMPLES / "verification"
CYCLE_S = 0.05
TOLERANCE_M = 0.01


def hook(page: Page, expression: str) -> Any:
    return page.evaluate(f"window.highbayViewer.{expression}")


def move_to(page: Page, time_s: float) -> None:
    page.evaluate(
        """(time) => {
            const slider = document.querySelector('#time-slider');
            slider.value = String(time);
            slider.dispatchEvent(new Event('input'));
        }""",
        time_s,
    )


@pytest.fixture
def output(tmp_path: Path) -> Path:
    arguments = [str(VERIFICATION / "v1-warehouse.yaml"), str(VERIFICATION / "v1-scenario.yaml")]
    path = tmp_path / "run"
    code = main(
        ["run", *arguments, "--output", str(path), "--time-stepped", "--replay", "--record-signals"]
    )
    assert code == 0
    return path


@pytest.fixture
def opened(page: Page, serve: Callable[[Path], str], output: Path) -> Page:
    page.goto(serve(output / "replay.json"))
    page.wait_for_function("window.highbayViewer !== undefined")
    page.evaluate("window.highbayViewer.ready")
    assert hook(page, "lastError") is None
    return page


def recorded_positions(output: Path) -> dict[int, tuple[float, float]]:
    """Return the crane's position at the start of every cycle, from the signal record."""
    rows = list(csv.DictReader((output / "signals.csv").read_text(encoding="utf-8").splitlines()))
    changes: dict[int, dict[str, float]] = {}
    for row in rows:
        if row["signal"] in ("horizontal_actual_m", "vertical_actual_m"):
            changes.setdefault(int(row["cycle"]), {})[row["signal"]] = float(row["value"])
    positions = {}
    horizontal = vertical = 0.0
    for cycle in range(max(changes) + 1):
        change = changes.get(cycle, {})
        horizontal = change.get("horizontal_actual_m", horizontal)
        vertical = change.get("vertical_actual_m", vertical)
        positions[cycle] = (horizontal, vertical)
    return positions


def test_viewer_opens_a_time_stepped_run_and_figures_equal_the_result(
    opened: Page, output: Path
) -> None:
    result = json.loads((output / "result.json").read_text(encoding="utf-8"))
    move_to(opened, 3600.0)
    summary = hook(opened, "summary()")
    assert summary["completed"] == result["metrics"]["order_outcomes"]["completed"] == 2
    assert summary["backlog"]["total"] == result["metrics"]["backlog_orders"]["at_window_end"]
    assert summary["occupancy"] == pytest.approx(
        result["metrics"]["storage_occupancy"]["at_window_end"]
    )
    assert summary["cranes"]["1"]["activity"] == "idle"


def test_crane_positions_equal_the_plant_at_cycle_boundaries(opened: Page, output: Path) -> None:
    positions = recorded_positions(output)
    # Storage moves from about 10 s to 17 s, and the retrieval from about 40 s to 47 s.
    cycles = [*range(200, 345, 7), *range(800, 945, 7)]
    assert len({positions[cycle] for cycle in cycles}) > 30
    for cycle in cycles:
        move_to(opened, cycle * CYCLE_S)
        actual = hook(opened, "crane(1)")["position"]
        assert actual == pytest.approx(positions[cycle], abs=TOLERANCE_M), cycle


def test_load_unit_is_in_the_expected_cell(opened: Page) -> None:
    # The only free cell is bay 3, level 2. Its load arrives at about 27 s, and is reserved at 30 s.
    cell = "cell([1, 1, 3, 2])"
    move_to(opened, 5.0)
    assert hook(opened, cell)["state"] != "occupied"
    move_to(opened, 29.0)
    assert hook(opened, cell)["state"] == "occupied"
    move_to(opened, 50.0)
    assert hook(opened, cell)["state"] == "free"


def test_replay_changes_no_other_output(tmp_path: Path) -> None:
    arguments = [str(VERIFICATION / "v1-warehouse.yaml"), str(VERIFICATION / "v1-scenario.yaml")]
    stepped = ["--time-stepped"]
    assert main(["run", *arguments, "--output", str(tmp_path / "a"), *stepped]) == 0
    assert main(["run", *arguments, "--output", str(tmp_path / "b"), *stepped, "--replay"]) == 0
    for name in ("report.md", "result.json", "orders.csv"):
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()
    replay = json.loads((tmp_path / "b" / "replay.json").read_text(encoding="utf-8"))
    assert replay["format_version"] == 1
    assert replay["run"]["execution"]["mode"] == "time_stepped"
