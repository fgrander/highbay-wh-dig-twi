"""User Story 3: warehouse designs changed in data only give comparable results."""

import csv
import json
from pathlib import Path
from typing import Any

import pytest

from highbay_sim.cli import main

ROOT = Path(__file__).parents[2]
BASE = ROOT / "samples" / "small-warehouse.yaml"
VARIANTS = ROOT / "samples" / "variants"
DAILY = ROOT / "samples" / "daily-scenario.yaml"
SPACED = VARIANTS / "spaced-orders.yaml"
VARIANT_FILES = [
    VARIANTS / f"{name}.yaml"
    for name in (
        "higher-speed",
        "more-aisles",
        "different-cells",
        "random-free",
        "transfer-both-ends",
    )
]


def run(
    warehouse: Path, scenario: Path, output: Path
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    assert main(["run", str(warehouse), str(scenario), "--output", str(output)]) == 0
    result = json.loads((output / "result.json").read_text(encoding="utf-8"))
    rows = list(csv.DictReader((output / "orders.csv").read_text(encoding="utf-8").splitlines()))
    return result, rows


@pytest.fixture(scope="module")
def daily_runs(tmp_path_factory: pytest.TempPathFactory) -> dict[str, tuple[Any, Any]]:
    output = tmp_path_factory.mktemp("variants")
    return {
        warehouse.stem: run(warehouse, DAILY, output / warehouse.stem)
        for warehouse in [BASE, *VARIANT_FILES]
    }


def metric_names(result: dict[str, Any]) -> dict[str, Any]:
    """Return metric names at each level, without the crane numbers, which depend on the design."""
    names = {name: sorted(values) for name, values in result["metrics"].items()}
    names["crane_utilization"] = sorted(result["metrics"]["crane_utilization"]["1"])
    return names


def test_every_variant_runs_and_differs_from_the_base(daily_runs: dict[str, Any]) -> None:
    base_result, _ = daily_runs["small-warehouse"]
    for warehouse in VARIANT_FILES:
        result, _ = daily_runs[warehouse.stem]
        assert result["run"]["warehouse"]["name"] == warehouse.stem
        assert result["run"]["warehouse"]["sha256"] != base_result["run"]["warehouse"]["sha256"]
        assert result["metrics"] != base_result["metrics"]


def test_all_results_have_the_same_metric_names_and_units(daily_runs: dict[str, Any]) -> None:
    base_result, _ = daily_runs["small-warehouse"]
    for result, _ in daily_runs.values():
        assert metric_names(result) == metric_names(base_result)
        assert result["definitions"] == base_result["definitions"]


def test_generated_orders_are_identical_across_variants(daily_runs: dict[str, Any]) -> None:
    def sequence(rows: list[dict[str, str]]) -> list[tuple[str, ...]]:
        return [(r["order_id"], r["type"], r["article"], r["arrival_s"]) for r in rows]

    _, base_rows = daily_runs["small-warehouse"]
    for _, rows in daily_runs.values():
        assert sequence(rows) == sequence(base_rows)


def test_each_aisle_count_reports_one_crane_per_aisle(daily_runs: dict[str, Any]) -> None:
    base_result, _ = daily_runs["small-warehouse"]
    more_aisles, _ = daily_runs["more-aisles"]
    assert set(base_result["metrics"]["crane_utilization"]) == {"1", "2", "3", "4"}
    assert set(more_aisles["metrics"]["crane_utilization"]) == {"1", "2", "3", "4", "5", "6"}


def test_transfer_point_variant_uses_the_configured_points(daily_runs: dict[str, Any]) -> None:
    def used(rows: list[dict[str, str]], order_type: str) -> set[str]:
        return {
            r["transfer_point"] for r in rows if r["type"] == order_type and r["transfer_point"]
        }

    _, base_rows = daily_runs["small-warehouse"]
    assert used(base_rows, "storage") == {"left"}
    assert used(base_rows, "retrieval") == {"right"}

    _, both_rows = daily_runs["transfer-both-ends"]
    assert used(both_rows, "retrieval") >= {"left"}
    assert used(both_rows, "storage") >= {"left", "right"}


def test_random_rule_changes_storage_cells(daily_runs: dict[str, Any]) -> None:
    def storage_cells(rows: list[dict[str, str]]) -> list[str]:
        return [r["location"] for r in rows if r["type"] == "storage"]

    _, base_rows = daily_runs["small-warehouse"]
    _, random_rows = daily_runs["random-free"]
    assert storage_cells(base_rows) != storage_cells(random_rows)


def test_cell_size_changes_order_times(daily_runs: dict[str, Any]) -> None:
    _, base_rows = daily_runs["small-warehouse"]
    _, cell_rows = daily_runs["different-cells"]
    assert [r["completion_s"] for r in base_rows] != [r["completion_s"] for r in cell_rows]


def test_faster_crane_shortens_orders_with_the_same_assignment(tmp_path: Path) -> None:
    def execution_time(row: dict[str, str]) -> float:
        return float(row["completion_s"]) - float(row["start_s"])

    _, slow = run(BASE, SPACED, tmp_path / "slow")
    _, fast = run(VARIANTS / "higher-speed.yaml", SPACED, tmp_path / "fast")

    assert len(slow) == len(fast) == 8
    for slow_order, fast_order in zip(slow, fast, strict=True):
        assert slow_order["outcome"] == fast_order["outcome"] == "completed"
        assert slow_order["start_s"] == slow_order["arrival_s"]
        assert fast_order["start_s"] == fast_order["arrival_s"]
        assert fast_order["location"] == slow_order["location"]
        assert execution_time(fast_order) < execution_time(slow_order)
