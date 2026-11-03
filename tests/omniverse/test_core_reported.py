"""SC-006: at the jump to the highest backlog, the state equals the reported value."""

import json
from pathlib import Path

import pytest

from conftest import SAMPLES, replay_data
from highbay.replay.core.recorded_source import RecordedSource
from highbay_sim.cli import main

REFERENCE_FILE = Path(__file__).parents[1] / "data" / "reference_results.json"
SAMPLE_PAIRS = sorted(json.loads(REFERENCE_FILE.read_text(encoding="utf-8")))


@pytest.mark.parametrize("pair", SAMPLE_PAIRS)
def test_backlog_at_the_peak_equals_the_reported_maximum(pair: str, tmp_path: Path) -> None:
    warehouse, scenario = pair.split(" ")
    arguments = [
        "run",
        str(SAMPLES / warehouse),
        str(SAMPLES / scenario),
        "--output",
        str(tmp_path / "run"),
        "--replay",
    ]
    assert main(arguments) == 0
    data = replay_data(tmp_path / "run")
    reported = data["reported"]

    state = RecordedSource(data).state_at(reported["first_backlog_peak_s"])

    assert state.backlog.total == reported["backlog_orders"]["max_in_window"]
