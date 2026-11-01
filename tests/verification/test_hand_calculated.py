"""SC-003: results compared with values calculated by hand, independently of the code.

All scenarios use a warehouse with cells 4 m long and 3 m high, horizontal speed 2 m/s and
acceleration 1 m/s², vertical speed 1 m/s and acceleration 1 m/s², pick and set times of 10 s.
Travel time on an axis is d/v + v/a when d >= v²/a, otherwise 2·sqrt(d/a).
"""

import csv
import json
from pathlib import Path
from typing import Any

import pytest

from highbay_sim.cli import main

SAMPLES = Path(__file__).parents[2] / "samples" / "verification"
TOLERANCE = 0.001  # 0.1%


def run(warehouse: str, scenario: str, output: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    code = main(["run", str(SAMPLES / warehouse), str(SAMPLES / scenario), "--output", str(output)])
    assert code == 0
    result = json.loads((output / "result.json").read_text(encoding="utf-8"))
    rows = list(csv.DictReader((output / "orders.csv").read_text(encoding="utf-8").splitlines()))
    return result, rows


def close(actual: float, expected: float) -> None:
    assert actual == pytest.approx(expected, rel=TOLERANCE, abs=1e-9)


def test_v1_store_then_retrieve(tmp_path: Path) -> None:
    # The only free cell is bay 3, level 2: 10 m along the aisle and 3 m up.
    # Horizontal: 10/2 + 2/1 = 7 s. Vertical: 3/1 + 1/1 = 4 s. The movement takes 7 s.
    # Right end is at 20 m, so the cell is 10 m from it too: 7 s.
    #   Storage:    pick 0-10, move 10-17, set 17-27.
    #   Idle 27-30.
    #   Retrieval:  no empty move, pick 30-40, move 40-47, set 47-57.
    result, rows = run("v1-warehouse.yaml", "v1-scenario.yaml", tmp_path)
    metrics = result["metrics"]

    close(float(rows[0]["completion_s"]), 27.0)
    close(float(rows[1]["completion_s"]), 57.0)
    assert [row["start_s"] for row in rows] == ["0.000", "30.000"]

    # Two completed orders in one hour.
    close(metrics["throughput_per_hour"]["total"], 2.0)
    close(metrics["throughput_per_hour"]["storage"], 1.0)
    close(metrics["throughput_per_hour"]["retrieval"], 1.0)

    for statistic in ("mean", "median", "p95", "max"):
        close(metrics["order_cycle_time_s"][statistic], 27.0)
        close(metrics["order_waiting_time_s"][statistic], 0.0)

    # Loaded: 7 + 7 = 14 s. Handling: 4 x 10 = 40 s. Idle: 3600 - 54 = 3546 s.
    crane = metrics["crane_utilization"]["1"]
    close(crane["moving_loaded"], 14.0 / 3600.0)
    close(crane["moving_empty"], 0.0)
    close(crane["handling"], 40.0 / 3600.0)
    close(crane["idle"], 3546.0 / 3600.0)

    # 9 of 10 cells at both ends of the window: one load unit came and went.
    close(metrics["storage_occupancy"]["at_window_start"], 0.9)
    close(metrics["storage_occupancy"]["at_window_end"], 0.9)
    assert metrics["backlog_orders"] == {"at_window_end": 0, "max_in_window": 0}


def test_v2_transfer_points_at_both_ends_use_the_nearer_one(tmp_path: Path) -> None:
    # The only free cell is bay 2, level 2: 6 m along the aisle and 3 m up.
    # Via left: horizontal 6/2 + 2/1 = 5 s, vertical 4 s, so 5 s.
    # Via right: 14 m, horizontal 14/2 + 2/1 = 9 s, so 9 s. The left end is nearer.
    #   Storage:    pick 0-10, move 10-15, set 15-25.
    #   Retrieval:  pick 30-40, move 40-45, set 45-55.
    _, rows = run("v2-warehouse.yaml", "v2-scenario.yaml", tmp_path)
    close(float(rows[0]["completion_s"]), 25.0)
    close(float(rows[1]["completion_s"]), 55.0)
    assert [row["transfer_point"] for row in rows] == ["left", "left"]


def test_v3_warm_up_limits_the_measurement_window(tmp_path: Path) -> None:
    # V1 timeline with a window from 20 s to 3600 s, which is 3580 s long.
    result, _ = run("v1-warehouse.yaml", "v3-scenario.yaml", tmp_path)
    metrics = result["metrics"]

    assert result["run"]["window"] == {"start_s": 20.0, "end_s": 3600.0}
    # Both orders complete in the window, at 27 s and 57 s.
    close(metrics["throughput_per_hour"]["total"], 2.0 * 3600.0 / 3580.0)
    close(metrics["order_cycle_time_s"]["mean"], 27.0)

    # Loaded: 10-17 is before the window, leaving 40-47, which is 7 s.
    # Handling: 17-27 counts 20-27 = 7 s, plus 30-40 and 47-57, which is 27 s.
    # Idle: 3580 - 34 = 3546 s.
    crane = metrics["crane_utilization"]["1"]
    close(crane["moving_loaded"], 7.0 / 3580.0)
    close(crane["moving_empty"], 0.0)
    close(crane["handling"], 27.0 / 3580.0)
    close(crane["idle"], 3546.0 / 3580.0)

    # Only the retrieval starts in the window, at 30 s, with no wait. A larger value would
    # show the storage order being counted, but both wait 0 s, so the count is what matters.
    assert metrics["order_waiting_time_s"]["max"] == 0.0

    # At 20 s the storage load is still on the crane, so 9 of 10 cells hold a load unit.
    close(metrics["storage_occupancy"]["at_window_start"], 0.9)
    close(metrics["storage_occupancy"]["at_window_end"], 0.9)
