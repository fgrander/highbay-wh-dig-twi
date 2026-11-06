"""The PLC commands and options of the command-line interface."""

import json
import subprocess
import sys
from functools import partial
from pathlib import Path
from typing import Any

import pytest

import highbay_sim.cli as cli
from data.memory_plc import MemoryPlc
from highbay_sim.cli import EXIT_FAILURE, EXIT_INVALID_INPUT, EXIT_SUCCESS, main
from highbay_sim.plc.controller import PlcController
from highbay_sim.plc.interface import PlcInterface
from highbay_sim.plc.link import LinkUnavailable, PlcConnection

ROOT = Path(__file__).parents[2]
WAREHOUSE = str(ROOT / "samples" / "verification" / "v1-warehouse.yaml")
SCENARIO = str(ROOT / "tests" / "data" / "plc-scenario.yaml")
SOURCE_FILES = ("HB_Types.udt", "HB_Interface.db", "HB_Control.scl")
BLOCK_LIBRARY = (
    "import sys\n"
    "sys.modules['s7commplus'] = None\n"
    "from highbay_sim.cli import main\n"
    "sys.exit(main(sys.argv[1:]))\n"
)


def run_blocked(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", BLOCK_LIBRARY, *arguments],
        capture_output=True,
        text=True,
        check=False,
    )


# plc-source


def test_plc_source_writes_the_three_files(tmp_path: Path) -> None:
    assert main(["plc-source", WAREHOUSE, "--output", str(tmp_path / "s")]) == EXIT_SUCCESS
    for name in SOURCE_FILES:
        assert (tmp_path / "s" / name).is_file()


def test_plc_source_gives_identical_files(tmp_path: Path) -> None:
    for directory in ("a", "b"):
        assert main(["plc-source", WAREHOUSE, "--output", str(tmp_path / directory)]) == 0
    for name in SOURCE_FILES:
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()


def test_plc_source_keeps_existing_files_without_overwrite(tmp_path: Path) -> None:
    output = tmp_path / "s"
    assert main(["plc-source", WAREHOUSE, "--output", str(output)]) == EXIT_SUCCESS
    (output / SOURCE_FILES[0]).write_text("mine", encoding="utf-8")
    assert main(["plc-source", WAREHOUSE, "--output", str(output)]) == EXIT_FAILURE
    assert (output / SOURCE_FILES[0]).read_text(encoding="utf-8") == "mine"
    arguments = ["plc-source", WAREHOUSE, "--output", str(output), "--overwrite"]
    assert main(arguments) == EXIT_SUCCESS
    assert (output / SOURCE_FILES[0]).read_text(encoding="utf-8") != "mine"


def test_plc_source_passes_the_cycle_time_on(tmp_path: Path) -> None:
    output = tmp_path / "s"
    assert main(["plc-source", WAREHOUSE, "--output", str(output), "--cycle-ms", "20"]) == 0
    assert "T#60ms" in (output / "HB_Control.scl").read_text(encoding="utf-8")


def test_plc_source_reports_an_invalid_warehouse(tmp_path: Path) -> None:
    missing = str(tmp_path / "missing.yaml")
    arguments = ["plc-source", missing, "--output", str(tmp_path / "s")]
    assert main(arguments) == EXIT_INVALID_INPUT


def test_plc_source_works_with_the_library_blocked(tmp_path: Path) -> None:
    output = tmp_path / "s"
    result = run_blocked("plc-source", WAREHOUSE, "--output", str(output))
    assert result.returncode == EXIT_SUCCESS, result.stderr
    assert (output / "HB_Control.scl").is_file()


# run --plc-host


@pytest.fixture
def plc(monkeypatch: pytest.MonkeyPatch) -> MemoryPlc:
    """The command line talks to a MemoryPlc, with that PLC's time in place of the system clock."""
    memory = MemoryPlc(PlcInterface(1))
    connections: list[PlcConnection] = []

    def open_memory(connection: PlcConnection) -> MemoryPlc:
        connections.append(connection)
        return memory

    memory.connections = connections  # type: ignore[attr-defined]
    monkeypatch.setattr(cli, "open_link", open_memory)
    monkeypatch.setattr(
        cli, "PlcController", partial(PlcController, clock=memory.now, wait=memory.wait)
    )
    return memory


def plc_run(output: Path, *options: str) -> int:
    return main(
        [
            "run",
            WAREHOUSE,
            SCENARIO,
            "--output",
            str(output),
            "--time-stepped",
            "--plc-host",
            "plc.example",
            *options,
        ]
    )


def result_of(output: Path) -> dict[str, Any]:
    return json.loads((output / "result.json").read_text(encoding="utf-8"))


def test_plc_host_needs_time_stepped(tmp_path: Path) -> None:
    arguments = ["run", WAREHOUSE, SCENARIO, "--output", str(tmp_path), "--plc-host", "x"]
    with pytest.raises(SystemExit) as stopped:
        main(arguments)
    assert stopped.value.code == EXIT_INVALID_INPUT


def test_plc_tls_ca_needs_plc_host(tmp_path: Path) -> None:
    arguments = [
        "run",
        WAREHOUSE,
        SCENARIO,
        "--output",
        str(tmp_path),
        "--time-stepped",
        "--plc-tls-ca",
        "ca.pem",
    ]
    with pytest.raises(SystemExit) as stopped:
        main(arguments)
    assert stopped.value.code == EXIT_INVALID_INPUT


def test_plc_host_cannot_be_used_with_a_controller(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as stopped:
        plc_run(tmp_path, "--controller", "file.py:Class")
    assert stopped.value.code == EXIT_INVALID_INPUT


def test_a_run_writes_outputs_and_closes_the_link(plc: MemoryPlc, tmp_path: Path) -> None:
    assert plc_run(tmp_path / "out") == EXIT_SUCCESS
    result = result_of(tmp_path / "out")
    assert result["plc"]["reproducible"] is False
    assert result["plc"]["stop_reason"] == "finished"
    assert result["run"]["execution"]["controller"]["name"] == "plc"
    assert plc.closed


def test_a_refused_device_writes_no_outputs(plc: MemoryPlc, tmp_path: Path) -> None:
    plc.device = "1;6ES7 511-1AK02-0AB0;V2.9"
    assert plc_run(tmp_path / "out") == EXIT_INVALID_INPUT
    assert not (tmp_path / "out" / "result.json").exists()
    assert plc.write_requests == []


def test_a_plc_not_in_run_writes_no_outputs(plc: MemoryPlc, tmp_path: Path) -> None:
    plc.state = "STOP"
    assert plc_run(tmp_path / "out") == EXIT_INVALID_INPUT
    assert not (tmp_path / "out" / "result.json").exists()


def test_a_differing_interface_writes_no_outputs(
    plc: MemoryPlc, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    plc.overrides["HB_Interface.crane_1.job_id"] = None
    assert plc_run(tmp_path / "out") == EXIT_INVALID_INPUT
    assert not (tmp_path / "out" / "result.json").exists()
    assert "HB_Interface.crane_1.job_id" in capsys.readouterr().err


def test_a_stopped_run_writes_its_outputs_and_exits_with_failure(
    plc: MemoryPlc, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    plc.fail_on_request = 500
    assert plc_run(tmp_path / "out") == EXIT_FAILURE
    result = result_of(tmp_path / "out")
    assert result["plc"]["stop_reason"] == "connection_lost"
    assert "cycle" in capsys.readouterr().err


def test_a_signal_file_is_kept_when_a_run_stops(plc: MemoryPlc, tmp_path: Path) -> None:
    plc.fail_on_request = 500
    assert plc_run(tmp_path / "out", "--record-signals") == EXIT_FAILURE
    assert (tmp_path / "out" / "signals.csv").stat().st_size > 0


def test_outputs_hold_neither_host_nor_password(
    plc: MemoryPlc,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("HIGHBAY_PLC_PASSWORD", "s3cret-value")
    assert plc_run(tmp_path / "out") == EXIT_SUCCESS
    printed = capsys.readouterr()
    texts = [printed.out, printed.err]
    texts += [path.read_text(encoding="utf-8") for path in (tmp_path / "out").iterdir()]
    for text in texts:
        assert "s3cret-value" not in text
        assert "plc.example" not in text


def test_the_password_comes_only_from_the_environment(
    plc: MemoryPlc, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HIGHBAY_PLC_PASSWORD", "s3cret-value")
    assert plc_run(tmp_path / "out", "--plc-tls-ca", "ca.pem") == EXIT_SUCCESS
    connection = plc.connections[0]  # type: ignore[attr-defined]
    assert connection == PlcConnection("plc.example", "ca.pem", "s3cret-value")
    parser = cli._parser()
    assert "password" not in parser.format_help().lower()
    with pytest.raises(SystemExit):
        plc_run(tmp_path / "other", "--plc-password", "x")


def test_an_empty_password_counts_as_none(
    plc: MemoryPlc, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HIGHBAY_PLC_PASSWORD", "")
    assert plc_run(tmp_path / "out") == EXIT_SUCCESS
    assert plc.connections[0].password is None  # type: ignore[attr-defined]


def test_a_stop_during_the_warmup_still_writes_outputs(plc: MemoryPlc, tmp_path: Path) -> None:
    scenario = tmp_path / "warmup.yaml"
    text = Path(SCENARIO).read_text(encoding="utf-8")
    scenario.write_text(text.replace("warmup_s: 0", "warmup_s: 60"), encoding="utf-8")
    plc.fail_on_request = 100
    arguments = [
        "run",
        WAREHOUSE,
        str(scenario),
        "--output",
        str(tmp_path / "out"),
        "--time-stepped",
        "--plc-host",
        "plc.example",
    ]
    assert main(arguments) == EXIT_FAILURE
    result = result_of(tmp_path / "out")
    assert result["plc"]["warmup_skipped"] is True
    assert "metrics cover all of it" in (tmp_path / "out" / "report.md").read_text(encoding="utf-8")


def test_a_missing_extra_is_invalid_input(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def unavailable(connection: PlcConnection) -> MemoryPlc:
        raise LinkUnavailable("the PLC connection is not installed, run: uv sync --extra plc")

    monkeypatch.setattr(cli, "open_link", unavailable)
    assert plc_run(tmp_path / "out") == EXIT_INVALID_INPUT
    assert "uv sync --extra plc" in capsys.readouterr().err


# plc-measure


def test_plc_measure_prints_the_figures(plc: MemoryPlc, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["plc-measure", WAREHOUSE, "--plc-host", "x", "--seconds", "1"]) == EXIT_SUCCESS
    printed = capsys.readouterr().out
    assert "6ES7 SIM-" in printed
    assert "median" in printed
    assert plc.closed


def test_plc_measure_lasts_60_seconds_by_default(plc: MemoryPlc) -> None:
    started = plc.now()
    assert main(["plc-measure", WAREHOUSE, "--plc-host", "x"]) == EXIT_SUCCESS
    assert plc.now() - started == pytest.approx(60.0, abs=0.5)


def test_plc_measure_needs_a_host() -> None:
    with pytest.raises(SystemExit) as stopped:
        main(["plc-measure", WAREHOUSE])
    assert stopped.value.code == EXIT_INVALID_INPUT


def test_plc_measure_refuses_an_unconfirmed_device(plc: MemoryPlc) -> None:
    plc.device = None
    arguments = ["plc-measure", WAREHOUSE, "--plc-host", "x", "--seconds", "1"]
    assert main(arguments) == EXIT_INVALID_INPUT
    assert plc.write_requests == []


def test_plc_measure_reports_a_lost_connection(
    plc: MemoryPlc, capsys: pytest.CaptureFixture[str]
) -> None:
    plc.fail_on_request = 50
    arguments = ["plc-measure", WAREHOUSE, "--plc-host", "x", "--seconds", "60"]
    assert main(arguments) == EXIT_FAILURE
    assert "connection_lost" in capsys.readouterr().err


def test_plc_measure_says_how_to_install_a_missing_extra(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def unavailable(connection: PlcConnection) -> MemoryPlc:
        raise LinkUnavailable("the PLC connection is not installed, run: uv sync --extra plc")

    monkeypatch.setattr(cli, "open_link", unavailable)
    arguments = ["plc-measure", WAREHOUSE, "--plc-host", "x", "--seconds", "1"]
    assert main(arguments) == EXIT_INVALID_INPUT
    assert "uv sync --extra plc" in capsys.readouterr().err
