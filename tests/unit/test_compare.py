"""Comparing the results of two runs."""

import copy
from typing import Any

import pytest

from highbay_sim.compare import ComparisonError, compare_results


def result(**execution: Any) -> dict[str, Any]:
    document: dict[str, Any] = {
        "run": {
            "warehouse": {"name": "w", "sha256": "aaa"},
            "scenario": {"name": "s", "sha256": "bbb"},
        },
        "metrics": {
            "throughput_per_hour": {"total": 100.0, "storage": 60.0, "retrieval": 40.0},
            "order_cycle_time_s": {"mean": 20.0, "max": None},
            "crane_utilization": {"1": {"idle": 0.0}},
            "backlog_orders": {"at_window_end": 4},
        },
    }
    if execution:
        document["run"]["execution"] = execution
    return document


def stepped() -> dict[str, Any]:
    document = result(mode="time_stepped", cycle_ms=50)
    document["metrics"]["throughput_per_hour"]["total"] = 99.0
    document["metrics"]["crane_utilization"]["1"]["idle"] = 0.5
    return document


def row(text: str, metric: str) -> str:
    return next(line for line in text.splitlines() if metric in line)


def test_shows_each_metric_with_both_values_and_its_deviation() -> None:
    text = compare_results(result(), stepped())
    line = row(text, "throughput_per_hour.total")
    assert "100.0" in line
    assert "99.0" in line
    assert "-1" in line
    assert "-1.00%" in line
    assert "throughput_per_hour.storage" in text
    assert "backlog_orders.at_window_end" in text


def test_a_value_of_zero_in_the_first_run_shows_only_the_absolute_deviation() -> None:
    line = row(compare_results(result(), stepped()), "crane_utilization.1.idle")
    assert "0.5" in line
    assert "%" not in line


def test_identical_runs_show_no_deviation() -> None:
    line = row(compare_results(result(), copy.deepcopy(result())), "throughput_per_hour.total")
    assert "0.00%" in line


def test_a_value_that_is_not_available_is_shown_as_such() -> None:
    line = row(compare_results(result(), result()), "order_cycle_time_s.max")
    assert "not available" in line


def test_shows_how_each_run_was_executed() -> None:
    text = compare_results(result(), stepped())
    assert "A: event-based" in text
    assert "B: time-stepped, 50 ms" in text


@pytest.mark.parametrize("part", ["warehouse", "scenario"])
def test_different_inputs_are_refused_naming_the_difference(part: str) -> None:
    other = result()
    other["run"][part]["sha256"] = "different"
    with pytest.raises(ComparisonError, match=part):
        compare_results(result(), other)
