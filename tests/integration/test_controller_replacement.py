"""SC-007: controllers replace the built-in one with no change to the plant model."""

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from highbay_sim.cli import main

ROOT = Path(__file__).parents[2]
WAREHOUSE = str(ROOT / "samples" / "verification" / "v1-warehouse.yaml")
SCENARIO = str(ROOT / "samples" / "verification" / "v1-scenario.yaml")
SCRIPTED = ROOT / "tests" / "data" / "scripted_controller.py"


def stepped(output: Path, controller: str) -> int:
    return main(
        [
            "run",
            WAREHOUSE,
            SCENARIO,
            "--output",
            str(output),
            "--time-stepped",
            "--controller",
            controller,
        ]
    )


def result_of(output: Path) -> dict[str, Any]:
    return json.loads((output / "result.json").read_text(encoding="utf-8"))


def controller_file(tmp_path: Path, body: str) -> str:
    path = tmp_path / "my_controller.py"
    path.write_text(f"class My:\n    def scan(self, signals):\n{body}\n", encoding="utf-8")
    return f"{path}:My"


def test_scripted_controller_stores_and_retrieves_as_expected(tmp_path: Path) -> None:
    assert stepped(tmp_path / "out", f"{SCRIPTED}:ScriptedController") == 0
    result = result_of(tmp_path / "out")
    assert result["metrics"]["order_outcomes"]["completed"] == 2
    assert result["metrics"]["storage_occupancy"]["at_window_end"] == 0.9
    assert result["faults"] == []


def test_the_run_records_the_controller_and_its_hash(tmp_path: Path) -> None:
    assert stepped(tmp_path / "out", f"{SCRIPTED}:ScriptedController") == 0
    controller = result_of(tmp_path / "out")["run"]["execution"]["controller"]
    assert controller["name"] == "scripted_controller.py:ScriptedController"
    assert controller["sha256"] == hashlib.sha256(SCRIPTED.read_bytes()).hexdigest()


@pytest.mark.parametrize(
    "controller",
    ["missing.py:Nothing", f"{SCRIPTED}:Nothing", str(SCRIPTED), f"{SCRIPTED}:Step"],
)
def test_a_controller_that_cannot_be_loaded_exits_with_code_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], controller: str
) -> None:
    assert stepped(tmp_path / "out", controller) == 2
    assert "controller" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


def test_a_class_with_no_scan_method_exits_with_code_2(tmp_path: Path) -> None:
    path = tmp_path / "no_scan.py"
    path.write_text("class My:\n    pass\n", encoding="utf-8")
    assert stepped(tmp_path / "out", f"{path}:My") == 2


def test_a_controller_file_with_an_error_exits_with_code_2(tmp_path: Path) -> None:
    path = tmp_path / "broken.py"
    path.write_text("this is not python\n", encoding="utf-8")
    assert stepped(tmp_path / "out", f"{path}:My") == 2


def test_a_controller_raising_an_error_stops_the_run_with_code_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    controller = controller_file(tmp_path, "        raise ValueError('broken controller')")
    assert stepped(tmp_path / "out", controller) == 1
    error = capsys.readouterr().err
    assert "cycle 0" in error
    assert "broken controller" in error
    assert not (tmp_path / "out" / "result.json").exists()


def test_an_invalid_command_gives_a_fault_and_exit_code_0(tmp_path: Path) -> None:
    body = (
        "        signals[1].horizontal_target_m = 999.0\n        signals[1].horizontal_start = True"
    )
    assert stepped(tmp_path / "out", controller_file(tmp_path, body)) == 0
    faults = result_of(tmp_path / "out")["faults"]
    assert [fault["name"] for fault in faults] == ["target_out_of_range"]
    assert faults[0]["crane"] == 1
    report = (tmp_path / "out" / "report.md").read_text(encoding="utf-8")
    assert "target_out_of_range" in report


def test_a_controller_doing_nothing_leaves_orders_open(tmp_path: Path) -> None:
    assert stepped(tmp_path / "out", controller_file(tmp_path, "        pass")) == 0
    outcomes = result_of(tmp_path / "out")["metrics"]["order_outcomes"]
    assert outcomes["completed"] == 0
    assert outcomes["unfinished"] > 0


def test_claiming_a_job_done_without_doing_it_completes_no_order(tmp_path: Path) -> None:
    body = "        signals[1].job_done_id = signals[1].job_id"
    assert stepped(tmp_path / "out", controller_file(tmp_path, body)) == 0
    assert result_of(tmp_path / "out")["metrics"]["order_outcomes"]["completed"] == 0


def test_controller_option_needs_time_stepped(tmp_path: Path) -> None:
    arguments = ["run", WAREHOUSE, SCENARIO, "--output", str(tmp_path / "out")]
    with pytest.raises(SystemExit) as stopped:
        main([*arguments, "--controller", f"{SCRIPTED}:ScriptedController"])
    assert stopped.value.code == 2


def test_setting_a_load_in_another_cell_completes_no_order(tmp_path: Path) -> None:
    # This warehouse has one free cell at bay 3, level 2, so storing elsewhere is a fault, and
    # the job stays open. Run with a controller that sets the load back at the inbound end's bay.
    body = """        crane = signals[1]
        if crane.job_id == 0 or crane.load_present and crane.handling_active:
            return
        crane.pick_start = not crane.load_present
        crane.set_start = False
        if crane.load_present and crane.horizontal_in_position:
            crane.horizontal_target_m = 2.0
            crane.horizontal_start = True
        if crane.load_present and crane.horizontal_actual_m == 2.0:
            crane.side = 1
            crane.set_start = True
"""
    assert stepped(tmp_path / "out", controller_file(tmp_path, body)) == 0
    assert result_of(tmp_path / "out")["metrics"]["order_outcomes"]["completed"] == 0
