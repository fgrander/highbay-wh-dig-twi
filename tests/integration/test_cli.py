import csv
import json
from pathlib import Path

import pytest

from conftest import minimal_scenario_dict, minimal_warehouse_dict, write_yaml
from highbay_sim import __version__
from highbay_sim.cli import main

ROOT = Path(__file__).parents[2]
WAREHOUSE = str(ROOT / "samples" / "small-warehouse.yaml")
SCENARIO = str(ROOT / "samples" / "daily-scenario.yaml")
ORDER_HEADER = (
    "order_id,type,article,arrival_s,start_s,completion_s,crane,location,"
    "transfer_point,outcome,reason"
)


def run_sample(output: Path) -> int:
    return main(["run", WAREHOUSE, SCENARIO, "--output", str(output)])


def test_validate_success(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["validate", WAREHOUSE, SCENARIO]) == 0
    printed = capsys.readouterr().out
    assert "4 aisles" in printed
    assert "3200 cells" in printed


def test_validate_failure_reports_problem_in_contract_format(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    content = minimal_warehouse_dict()
    content["layout"]["aisle_count"] = 0
    path = write_yaml(tmp_path / "warehouse.yaml", content)
    assert main(["validate", str(path), SCENARIO]) == 2
    error = capsys.readouterr().err
    assert f"{path}: layout.aisle_count: " in error


def test_run_writes_all_outputs_and_prints_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "out"
    assert run_sample(output) == 0
    assert (output / "report.md").is_file()
    assert (output / "result.json").is_file()
    assert (output / "orders.csv").is_file()
    printed = capsys.readouterr().out
    assert str(output) in printed
    assert "orders/hour" in printed


def test_result_json_follows_contract(tmp_path: Path) -> None:
    output = tmp_path / "out"
    assert run_sample(output) == 0
    result = json.loads((output / "result.json").read_text(encoding="utf-8"))

    run = result["run"]
    assert run["software_version"] == __version__
    assert run["seed"] == 42
    assert run["warehouse"]["name"] == "small-warehouse"
    assert len(run["warehouse"]["sha256"]) == 64
    assert run["scenario"]["name"] == "daily-scenario"
    assert run["duration_s"] == 86400.0
    assert run["window"] == {"start_s": 3600.0, "end_s": 86400.0}

    metrics = result["metrics"]
    assert set(metrics["throughput_per_hour"]) == {"total", "storage", "retrieval"}
    for statistics in ("order_cycle_time_s", "order_waiting_time_s"):
        assert set(metrics[statistics]) == {"mean", "median", "p95", "max"}
    assert set(metrics["crane_utilization"]) == {"1", "2", "3", "4"}
    assert set(metrics["crane_utilization"]["1"]) == {
        "moving_loaded",
        "moving_empty",
        "handling",
        "idle",
    }
    assert set(metrics["backlog_orders"]) == {"at_window_end", "max_in_window"}
    assert set(metrics["storage_occupancy"]) == {"at_window_start", "at_window_end"}
    assert set(metrics["order_outcomes"]) == {
        "generated",
        "completed",
        "unfinished",
        "unfulfillable",
    }
    assert metrics["order_outcomes"]["completed"] > 0
    assert metrics["throughput_per_hour"]["total"] > 0

    assert set(result["definitions"]) == set(metrics)
    for entry in result["definitions"].values():
        assert entry["unit"]
        assert entry["definition"]


def test_report_contains_every_metric_definition_and_seed(tmp_path: Path) -> None:
    output = tmp_path / "out"
    assert run_sample(output) == 0
    report = (output / "report.md").read_text(encoding="utf-8")
    for heading in (
        "Run identification",
        "Throughput",
        "Cycle and waiting times",
        "Crane utilization",
        "Backlog, occupancy, and order outcomes",
        "Metric definitions",
    ):
        assert heading in report
    result = json.loads((output / "result.json").read_text(encoding="utf-8"))
    for entry in result["definitions"].values():
        assert entry["definition"] in report
        assert entry["unit"] in report
    assert "Seed: 42" in report
    assert result["run"]["warehouse"]["sha256"] in report


def test_orders_csv_follows_contract(tmp_path: Path) -> None:
    output = tmp_path / "out"
    assert run_sample(output) == 0
    text = (output / "orders.csv").read_text(encoding="utf-8")
    assert text.splitlines()[0] == ORDER_HEADER
    rows = list(csv.DictReader(text.splitlines()))
    result = json.loads((output / "result.json").read_text(encoding="utf-8"))
    assert len(rows) == result["metrics"]["order_outcomes"]["generated"]
    assert [row["order_id"] for row in rows] == sorted(row["order_id"] for row in rows)
    completed = next(row for row in rows if row["outcome"] == "completed")
    assert len(completed["location"].split("-")) == 4
    assert completed["transfer_point"] in ("left", "right")
    assert completed["reason"] == ""
    assert "." in completed["arrival_s"]
    assert len(completed["arrival_s"].split(".")[1]) == 3


def test_outputs_are_not_replaced_without_overwrite(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "out"
    assert run_sample(output) == 0
    before = (output / "result.json").read_bytes()
    (output / "result.json").write_text("{}", encoding="utf-8")

    assert run_sample(output) == 1
    assert "--overwrite" in capsys.readouterr().err
    assert (output / "result.json").read_text(encoding="utf-8") == "{}"

    assert main(["run", WAREHOUSE, SCENARIO, "--output", str(output), "--overwrite"]) == 0
    assert (output / "result.json").read_bytes() == before


def test_invalid_input_starts_no_run(tmp_path: Path) -> None:
    content = minimal_scenario_dict()
    content["warmup_s"] = 3600
    scenario = write_yaml(tmp_path / "scenario.yaml", content)
    output = tmp_path / "out"
    assert main(["run", WAREHOUSE, str(scenario), "--output", str(output)]) == 2
    assert not output.exists()


def test_output_that_cannot_be_written_exits_with_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    blocking_file = tmp_path / "file"
    blocking_file.write_text("", encoding="utf-8")
    assert run_sample(blocking_file / "out") == 1
    assert capsys.readouterr().err


def test_version_prints_software_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as caught:
        main(["--version"])
    assert caught.value.code == 0
    assert __version__ in capsys.readouterr().out


@pytest.mark.parametrize("arguments", [[], ["run"], ["unknown"], ["run", "a", "b"]])
def test_incorrect_usage_exits_with_two(arguments: list[str]) -> None:
    with pytest.raises(SystemExit) as caught:
        main(arguments)
    assert caught.value.code == 2
