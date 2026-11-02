"""Time-stepped runs through the command-line interface."""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from highbay_sim.cli import main

ROOT = Path(__file__).parents[2]
WAREHOUSE = str(ROOT / "samples" / "verification" / "v1-warehouse.yaml")
SCENARIO = str(ROOT / "samples" / "verification" / "v1-scenario.yaml")
RESULT_FILES = ("report.md", "result.json", "orders.csv")


def stepped(output: Path, *options: str) -> int:
    return main(["run", WAREHOUSE, SCENARIO, "--output", str(output), "--time-stepped", *options])


def result_of(output: Path) -> dict[str, Any]:
    return json.loads((output / "result.json").read_text(encoding="utf-8"))


def test_writes_the_result_files(tmp_path: Path) -> None:
    assert stepped(tmp_path / "out") == 0
    for name in RESULT_FILES:
        assert (tmp_path / "out" / name).is_file()


def test_records_how_the_run_was_executed(tmp_path: Path) -> None:
    assert stepped(tmp_path / "out") == 0
    result = result_of(tmp_path / "out")
    assert result["run"]["execution"] == {
        "mode": "time_stepped",
        "cycle_ms": 50,
        "controller": {"name": "built-in", "sha256": None},
        "signal_list_version": 1,
    }
    assert result["faults"] == []


def test_cycle_time_can_be_chosen(tmp_path: Path) -> None:
    assert stepped(tmp_path / "out", "--cycle-ms", "10") == 0
    assert result_of(tmp_path / "out")["run"]["execution"]["cycle_ms"] == 10


def test_metrics_have_the_same_names_and_definitions_as_event_based_runs(tmp_path: Path) -> None:
    assert stepped(tmp_path / "stepped") == 0
    assert main(["run", WAREHOUSE, SCENARIO, "--output", str(tmp_path / "event")]) == 0
    stepped_result, event_result = result_of(tmp_path / "stepped"), result_of(tmp_path / "event")
    assert stepped_result["definitions"] == event_result["definitions"]
    assert stepped_result["metrics"].keys() == event_result["metrics"].keys()
    assert stepped_result["schema_version"] == event_result["schema_version"]


def test_event_based_runs_have_no_execution_details(tmp_path: Path) -> None:
    assert main(["run", WAREHOUSE, SCENARIO, "--output", str(tmp_path / "event")]) == 0
    result = result_of(tmp_path / "event")
    assert "execution" not in result["run"]
    assert "faults" not in result


def test_assumptions_name_the_sources_of_deviation(tmp_path: Path) -> None:
    assert stepped(tmp_path / "out") == 0
    assert main(["run", WAREHOUSE, SCENARIO, "--output", str(tmp_path / "event")]) == 0
    event_assumptions = result_of(tmp_path / "event")["assumptions"]
    added = [
        text for text in result_of(tmp_path / "out")["assumptions"] if text not in event_assumptions
    ]
    text = " ".join(added)
    assert "cycle boundary" in text
    assert "handshake" in text
    assert "ideal" in text.lower()


def test_report_has_execution_and_faults_sections(tmp_path: Path) -> None:
    assert stepped(tmp_path / "out") == 0
    report = (tmp_path / "out" / "report.md").read_text(encoding="utf-8")
    assert "## Execution" in report
    assert "## Faults" in report
    assert "time_stepped" in report or "Time-stepped" in report


@pytest.mark.parametrize("value", ["0", "1001", "-5"])
def test_cycle_time_out_of_range_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], value: str
) -> None:
    with pytest.raises(SystemExit) as stopped:
        stepped(tmp_path / "out", f"--cycle-ms={value}")
    assert stopped.value.code == 2
    error = capsys.readouterr().err
    assert value in error
    assert "1 to 1000" in error
    assert not (tmp_path / "out").exists()


def test_cycle_time_must_be_a_whole_number(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as stopped:
        stepped(tmp_path / "out", "--cycle-ms", "2.5")
    assert stopped.value.code == 2
    assert "1 to 1000" in capsys.readouterr().err


def test_cycle_time_without_time_stepped_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    arguments = ["run", WAREHOUSE, SCENARIO, "--output", str(tmp_path / "out"), "--cycle-ms", "50"]
    with pytest.raises(SystemExit) as stopped:
        main(arguments)
    assert stopped.value.code == 2
    assert "--time-stepped" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


def run_in_process(output: Path, hash_seed: str) -> None:
    environment = {**os.environ, "PYTHONHASHSEED": hash_seed}
    subprocess.run(
        [
            sys.executable,
            "-m",
            "highbay_sim.cli",
            "run",
            str(ROOT / "samples" / "small-warehouse.yaml"),
            str(ROOT / "samples" / "daily-scenario.yaml"),
            "--output",
            str(output),
            "--time-stepped",
            "--cycle-ms",
            "1000",
        ],
        check=True,
        env=environment,
        capture_output=True,
    )


def test_runs_in_different_processes_are_byte_identical(tmp_path: Path) -> None:
    run_in_process(tmp_path / "a", "1")
    run_in_process(tmp_path / "b", "2")
    for name in RESULT_FILES:
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()


def test_a_run_loads_no_display_or_server_module(tmp_path: Path) -> None:
    code = (
        "import sys; from highbay_sim.cli import main; "
        f"main(['run', {WAREHOUSE!r}, {SCENARIO!r}, '--output', {str(tmp_path / 'out')!r}, "
        "'--time-stepped']); "
        "assert not {'tkinter', 'webbrowser', 'http.server', 'highbay_sim.viewer_server'} "
        "& set(sys.modules)"
    )
    subprocess.run([sys.executable, "-c", code], check=True, capture_output=True)


def test_compare_prints_deviations_and_writes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert stepped(tmp_path / "stepped") == 0
    assert main(["run", WAREHOUSE, SCENARIO, "--output", str(tmp_path / "event")]) == 0
    before = sorted(path for path in tmp_path.rglob("*"))
    capsys.readouterr()
    assert (
        main(["compare", str(tmp_path / "event"), str(tmp_path / "stepped" / "result.json")]) == 0
    )
    printed = capsys.readouterr().out
    assert "throughput_per_hour.total" in printed
    assert "time-stepped, 50 ms" in printed
    assert sorted(path for path in tmp_path.rglob("*")) == before


def test_compare_refuses_results_of_different_inputs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["run", WAREHOUSE, SCENARIO, "--output", str(tmp_path / "a")]) == 0
    other = str(ROOT / "samples" / "verification" / "v3-scenario.yaml")
    assert main(["run", WAREHOUSE, other, "--output", str(tmp_path / "b")]) == 0
    assert main(["compare", str(tmp_path / "a"), str(tmp_path / "b")]) == 2
    assert "scenario" in capsys.readouterr().err


def test_compare_with_a_missing_or_damaged_file_exits_with_code_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["run", WAREHOUSE, SCENARIO, "--output", str(tmp_path / "a")]) == 0
    damaged = tmp_path / "damaged.json"
    damaged.write_text("{not json", encoding="utf-8")
    assert main(["compare", str(tmp_path / "a"), str(tmp_path / "missing")]) == 2
    assert "missing" in capsys.readouterr().err
    assert main(["compare", str(tmp_path / "a"), str(damaged)]) == 2
    assert "damaged.json" in capsys.readouterr().err


def test_signal_record_is_byte_identical_and_changes_no_other_output(tmp_path: Path) -> None:
    assert stepped(tmp_path / "plain") == 0
    assert stepped(tmp_path / "a", "--record-signals") == 0
    assert stepped(tmp_path / "b", "--record-signals") == 0
    assert not (tmp_path / "plain" / "signals.csv").exists()
    record = (tmp_path / "a" / "signals.csv").read_bytes()
    assert record == (tmp_path / "b" / "signals.csv").read_bytes()
    assert b"pick_start,true" in record
    for name in RESULT_FILES:
        assert (tmp_path / "plain" / name).read_bytes() == (tmp_path / "a" / name).read_bytes()


def test_an_existing_signal_record_needs_overwrite(tmp_path: Path) -> None:
    assert stepped(tmp_path / "out", "--record-signals") == 0
    assert stepped(tmp_path / "out", "--record-signals") == 1
    assert stepped(tmp_path / "out", "--record-signals", "--overwrite") == 0
    assert (tmp_path / "out" / "signals.csv").exists()


def test_overwriting_without_recording_deletes_the_signal_record(tmp_path: Path) -> None:
    assert stepped(tmp_path / "out", "--record-signals") == 0
    assert stepped(tmp_path / "out", "--overwrite") == 0
    assert not (tmp_path / "out" / "signals.csv").exists()


def test_record_signals_needs_time_stepped(tmp_path: Path) -> None:
    arguments = ["run", WAREHOUSE, SCENARIO, "--output", str(tmp_path / "out")]
    with pytest.raises(SystemExit) as stopped:
        main([*arguments, "--record-signals"])
    assert stopped.value.code == 2
