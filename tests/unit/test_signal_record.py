"""The optional record of signal changes."""

import csv
from pathlib import Path

from highbay_sim.signal_record import SignalRecorder
from highbay_sim.signals import SIGNALS, CraneSignals


def rows_of(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))


def test_first_rows_hold_every_signal_at_cycle_0(tmp_path: Path) -> None:
    path = tmp_path / "signals.csv"
    signals = {1: CraneSignals(), 2: CraneSignals()}
    with SignalRecorder(path, signals) as recorder:
        recorder.record(0, 0.0)
    rows = rows_of(path)
    assert len(rows) == 2 * len(SIGNALS)
    assert [row["signal"] for row in rows[: len(SIGNALS)]] == [signal.name for signal in SIGNALS]
    assert {row["crane"] for row in rows[: len(SIGNALS)]} == {"1"}
    assert {row["cycle"] for row in rows} == {"0"}


def test_later_rows_hold_changes_only_in_list_order(tmp_path: Path) -> None:
    path = tmp_path / "signals.csv"
    signals = {1: CraneSignals(), 2: CraneSignals()}
    with SignalRecorder(path, signals) as recorder:
        recorder.record(0, 0.0)
        recorder.record(1, 0.05)
        signals[2].horizontal_start = True
        signals[1].load_present = True
        signals[1].job_id = 3
        recorder.record(2, 0.1)
    assert rows_of(path)[2 * len(SIGNALS) :] == [
        {"cycle": "2", "time_s": "0.1", "crane": "1", "signal": "job_id", "value": "3"},
        {"cycle": "2", "time_s": "0.1", "crane": "1", "signal": "load_present", "value": "true"},
        {
            "cycle": "2",
            "time_s": "0.1",
            "crane": "2",
            "signal": "horizontal_start",
            "value": "true",
        },
    ]


def test_values_are_exact(tmp_path: Path) -> None:
    path = tmp_path / "signals.csv"
    signals = {1: CraneSignals()}
    with SignalRecorder(path, signals) as recorder:
        recorder.record(0, 0.0)
        signals[1].horizontal_actual_m = 1.0 / 3.0
        signals[1].load_present = False
        recorder.record(1, 0.05)
    row = rows_of(path)[-1]
    assert (row["signal"], float(row["value"])) == ("horizontal_actual_m", 1.0 / 3.0)
    assert rows_of(path)[0]["value"] == "0"
    false_rows = [item for item in rows_of(path) if item["signal"] == "load_present"]
    assert false_rows[0]["value"] == "false"


def test_file_has_unix_line_endings_and_a_header(tmp_path: Path) -> None:
    path = tmp_path / "signals.csv"
    with SignalRecorder(path, {1: CraneSignals()}) as recorder:
        recorder.record(0, 0.0)
    content = path.read_bytes()
    assert b"\r" not in content
    assert content.startswith(b"cycle,time_s,crane,signal,value\n")
