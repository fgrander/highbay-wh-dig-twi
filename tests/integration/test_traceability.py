import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from conftest import minimal_scenario_dict, minimal_warehouse_dict, write_yaml
from highbay_sim import __version__
from highbay_sim.cli import main

ROOT = Path(__file__).parents[2]
WAREHOUSE = ROOT / "samples" / "small-warehouse.yaml"
SCENARIO = ROOT / "samples" / "daily-scenario.yaml"


def run(warehouse: Path, scenario: Path, output: Path) -> tuple[dict[str, Any], str]:
    assert main(["run", str(warehouse), str(scenario), "--output", str(output)]) == 0
    result = json.loads((output / "result.json").read_text(encoding="utf-8"))
    return result, (output / "report.md").read_text(encoding="utf-8")


def rows(output: Path) -> list[dict[str, str]]:
    return list(csv.DictReader((output / "orders.csv").read_text(encoding="utf-8").splitlines()))


def independent_hash(path: Path) -> str:
    """Calculate the content hash from the input file without using the program's code."""

    def text_keys(value: Any) -> Any:
        if isinstance(value, dict):
            return {str(key): text_keys(item) for key, item in value.items()}
        if isinstance(value, list):
            return [text_keys(item) for item in value]
        return value

    content = text_keys(yaml.safe_load(path.read_text(encoding="utf-8")))
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def test_outputs_identify_the_run(tmp_path: Path) -> None:
    result, report = run(WAREHOUSE, SCENARIO, tmp_path)
    run_info = result["run"]
    assert run_info["software_version"] == __version__
    assert run_info["seed"] == 42
    assert run_info["window"] == {"start_s": 3600.0, "end_s": 86400.0}
    assert run_info["warehouse"]["name"] == "small-warehouse"
    assert run_info["scenario"]["name"] == "daily-scenario"

    assert f"Software version: {__version__}" in report
    assert "Seed: 42" in report
    assert "3600.000 s to 86400.000 s" in report
    assert "small-warehouse" in report
    assert "daily-scenario" in report
    assert run_info["warehouse"]["sha256"] in report
    assert run_info["scenario"]["sha256"] in report


def test_hashes_match_an_independent_calculation(tmp_path: Path) -> None:
    result, _ = run(WAREHOUSE, SCENARIO, tmp_path)
    assert result["run"]["warehouse"]["sha256"] == independent_hash(WAREHOUSE)
    assert result["run"]["scenario"]["sha256"] == independent_hash(SCENARIO)


def test_report_and_result_contain_the_modeling_assumptions(tmp_path: Path) -> None:
    result, report = run(WAREHOUSE, SCENARIO, tmp_path)
    assumptions = result["assumptions"]
    assert len(assumptions) >= 10
    assert "## Modeling assumptions and simplifications" in report
    for assumption in assumptions:
        assert assumption in report
    text = " ".join(assumptions).lower()
    for topic in ("one crane", "first-come", "same dimensions", "weight", "failures", "warm-up"):
        assert topic in text


def test_report_follows_the_contract_section_order(tmp_path: Path) -> None:
    _, report = run(WAREHOUSE, SCENARIO, tmp_path)
    positions = [
        report.index(f"## {heading}")
        for heading in (
            "Run identification",
            "Throughput",
            "Cycle and waiting times",
            "Crane utilization",
            "Backlog, occupancy, and order outcomes",
            "Metric definitions",
            "Modeling assumptions and simplifications",
        )
    ]
    assert positions == sorted(positions)


def test_orders_csv_records_location_and_transfer_point(tmp_path: Path) -> None:
    verification = ROOT / "samples" / "verification"
    run(verification / "v1-warehouse.yaml", verification / "v1-scenario.yaml", tmp_path)
    storage, retrieval = rows(tmp_path)
    assert (storage["order_id"], storage["type"], storage["article"]) == ("O000001", "storage", "A")
    assert storage["crane"] == "1"
    assert storage["location"] == "1-1-3-2"
    assert storage["transfer_point"] == "left"
    assert (storage["arrival_s"], storage["start_s"], storage["completion_s"]) == (
        "0.000",
        "0.000",
        "27.000",
    )
    assert retrieval["location"] == "1-1-3-2"
    assert retrieval["transfer_point"] == "right"
    for row in (storage, retrieval):
        assert row["outcome"] == "completed"
        assert row["reason"] == ""


def test_orders_csv_records_every_reason(tmp_path: Path) -> None:
    warehouse = minimal_warehouse_dict()
    warehouse["initial_stock"] = [
        {"location": {"aisle": 1, "rack": 1, "bay": bay, "level": level}, "article": "B"}
        for bay in range(1, 6)
        for level in (1, 2)
    ]
    scenario = minimal_scenario_dict()
    scenario["duration_s"] = 5
    scenario["orders"] = [
        {"time_s": 0, "type": "retrieval", "article": "MISSING"},
        {"time_s": 0, "type": "retrieval", "article": "B"},
        {"time_s": 1, "type": "storage", "article": "A"},
    ]
    run(
        write_yaml(tmp_path / "w.yaml", warehouse),
        write_yaml(tmp_path / "s.yaml", scenario),
        tmp_path / "out",
    )
    missing, running, waiting = rows(tmp_path / "out")
    assert (missing["outcome"], missing["reason"]) == ("unfulfillable", "no_stock")
    assert missing["start_s"] == missing["completion_s"] == missing["location"] == ""
    assert (running["outcome"], running["reason"]) == ("unfinished", "run_ended")
    assert running["start_s"] == "0.000"
    assert running["completion_s"] == ""
    assert (waiting["outcome"], waiting["reason"]) == ("unfinished", "no_free_cell")
    assert waiting["location"] == ""


def test_every_order_can_be_found_with_its_times_or_reason(tmp_path: Path) -> None:
    result, _ = run(WAREHOUSE, SCENARIO, tmp_path)
    records = rows(tmp_path)
    assert len(records) == result["metrics"]["order_outcomes"]["generated"]
    for record in records:
        assert record["arrival_s"]
        if record["outcome"] == "completed":
            assert record["start_s"]
            assert record["completion_s"]
        else:
            assert record["reason"]
