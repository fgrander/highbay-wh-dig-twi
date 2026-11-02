"""SC-004: time-stepped throughput compared with the event-based simulation.

Each throughput value may deviate by at most 1% or one completed order, whichever is larger.
The daily scenario is cut to 2 hours here, as its full day at 5 ms takes minutes. The full day was
checked once while building this feature, and was within the limit at 50 ms and at 5 ms.
"""

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from conftest import write_yaml
from highbay_sim.cli import main

SAMPLES = Path(__file__).parents[2] / "samples"
SAMPLE_PAIRS = (
    ("small-warehouse.yaml", "daily-scenario.yaml"),
    ("replay/overloaded-warehouse.yaml", "replay/busy-scenario.yaml"),
    ("verification/v1-warehouse.yaml", "verification/v1-scenario.yaml"),
    ("verification/v1-warehouse.yaml", "verification/v3-scenario.yaml"),
    ("verification/v2-warehouse.yaml", "verification/v2-scenario.yaml"),
)
CYCLE_TIMES_MS = (50, 5)
RELATIVE_LIMIT = 0.01
LONGEST_DURATION_S = 7200


def run(pair: tuple[str, str], output: Path, *options: str) -> dict[str, Any]:
    scenario = yaml.safe_load((SAMPLES / pair[1]).read_text(encoding="utf-8"))
    scenario["duration_s"] = min(scenario["duration_s"], LONGEST_DURATION_S)
    output.mkdir()
    scenario_path = write_yaml(output / "scenario.yaml", scenario)
    arguments = [str(SAMPLES / pair[0]), str(scenario_path)]
    assert main(["run", *arguments, "--output", str(output), *options]) == 0
    return json.loads((output / "result.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("pair", SAMPLE_PAIRS, ids=lambda pair: pair[1])
@pytest.mark.parametrize("cycle_ms", CYCLE_TIMES_MS)
def test_throughput_deviates_by_at_most_the_limit(
    tmp_path: Path, pair: tuple[str, str], cycle_ms: int
) -> None:
    event = run(pair, tmp_path / "event")
    stepped = run(pair, tmp_path / "stepped", "--time-stepped", f"--cycle-ms={cycle_ms}")
    window = event["run"]["window"]
    one_order_per_hour = 3600.0 / (window["end_s"] - window["start_s"])
    for name in ("total", "storage", "retrieval"):
        expected = event["metrics"]["throughput_per_hour"][name]
        actual = stepped["metrics"]["throughput_per_hour"][name]
        limit = max(RELATIVE_LIMIT * expected, one_order_per_hour)
        assert abs(actual - expected) <= limit + 1e-6, (name, expected, actual)
