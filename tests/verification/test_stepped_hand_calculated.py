"""SC-003: time-stepped results compared with the hand calculations in test_hand_calculated.py.

Each order has at most four steps: a move to the source, a pick, a move, and a set. Its completion
time may deviate by at most 2 cycles for each step.
"""

import csv
import json
from pathlib import Path
from typing import Any

import pytest

from highbay_sim.cli import main

SAMPLES = Path(__file__).parents[2] / "samples" / "verification"
STEPS_PER_ORDER = 4
CYCLE_TIMES_MS = (50, 10)


def run(
    warehouse: str, scenario: str, output: Path, cycle_ms: int
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    code = main(
        [
            "run",
            str(SAMPLES / warehouse),
            str(SAMPLES / scenario),
            "--output",
            str(output),
            "--time-stepped",
            f"--cycle-ms={cycle_ms}",
        ]
    )
    assert code == 0
    result = json.loads((output / "result.json").read_text(encoding="utf-8"))
    rows = list(csv.DictReader((output / "orders.csv").read_text(encoding="utf-8").splitlines()))
    return result, rows


def within_limit(actual: str, expected: float, cycle_ms: int) -> None:
    limit = 2 * STEPS_PER_ORDER * cycle_ms / 1000
    assert expected <= float(actual) <= expected + limit


@pytest.mark.parametrize("cycle_ms", CYCLE_TIMES_MS)
def test_v1_store_then_retrieve(tmp_path: Path, cycle_ms: int) -> None:
    # Storage: pick 0-10, move 10-17, set 17-27. Retrieval: pick 30-40, move 40-47, set 47-57.
    result, rows = run("v1-warehouse.yaml", "v1-scenario.yaml", tmp_path, cycle_ms)
    within_limit(rows[0]["completion_s"], 27.0, cycle_ms)
    within_limit(rows[1]["completion_s"], 57.0, cycle_ms)
    assert float(rows[1]["start_s"]) == 30.0
    assert result["metrics"]["throughput_per_hour"]["total"] == 2.0
    assert result["metrics"]["order_outcomes"]["completed"] == 2
    assert result["metrics"]["storage_occupancy"]["at_window_end"] == 0.9


@pytest.mark.parametrize("cycle_ms", CYCLE_TIMES_MS)
def test_v2_uses_the_nearer_transfer_point(tmp_path: Path, cycle_ms: int) -> None:
    # Storage: pick 0-10, move 10-15, set 15-25. Retrieval: pick 30-40, move 40-45, set 45-55.
    _, rows = run("v2-warehouse.yaml", "v2-scenario.yaml", tmp_path, cycle_ms)
    within_limit(rows[0]["completion_s"], 25.0, cycle_ms)
    within_limit(rows[1]["completion_s"], 55.0, cycle_ms)
    assert [row["transfer_point"] for row in rows] == ["left", "left"]


@pytest.mark.parametrize("cycle_ms", CYCLE_TIMES_MS)
def test_v3_uses_the_same_measurement_window(tmp_path: Path, cycle_ms: int) -> None:
    # Handling in the window: 17-27 counts 20-27, plus 30-40 and 47-57, which is 27 s of 3580 s.
    result, rows = run("v1-warehouse.yaml", "v3-scenario.yaml", tmp_path, cycle_ms)
    assert result["run"]["window"] == {"start_s": 20.0, "end_s": 3600.0}
    within_limit(rows[1]["completion_s"], 57.0, cycle_ms)
    crane = result["metrics"]["crane_utilization"]["1"]
    limit = 2 * STEPS_PER_ORDER * 2 * cycle_ms / 1000 / 3580.0
    assert crane["handling"] == pytest.approx(27.0 / 3580.0, abs=limit)
    assert crane["moving_loaded"] == pytest.approx(7.0 / 3580.0, abs=limit)
