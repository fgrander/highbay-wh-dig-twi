from pathlib import Path
from typing import Any

import pytest
import yaml

from highbay_sim.cli import main

ROOT = Path(__file__).parents[2]
INVALID = ROOT / "samples" / "invalid"
GOOD_WAREHOUSE = ROOT / "samples" / "small-warehouse.yaml"
GOOD_SCENARIO = ROOT / "samples" / "daily-scenario.yaml"


def cases() -> list[dict[str, Any]]:
    return yaml.safe_load((INVALID / "expected.yaml").read_text(encoding="utf-8"))


def arguments(case: dict[str, Any]) -> tuple[str, str]:
    path = INVALID / case["file"]
    if case["kind"] == "warehouse":
        return str(path), str(GOOD_SCENARIO)
    return str(GOOD_WAREHOUSE), str(path)


def test_expected_list_covers_every_invalid_sample() -> None:
    listed = {case["file"] for case in cases()}
    present = {path.name for path in INVALID.glob("*.yaml")} - {"expected.yaml"}
    assert listed == present
    assert len(listed) >= 11


@pytest.mark.parametrize("case", cases(), ids=lambda case: case["file"])
def test_invalid_sample_is_rejected_with_each_expected_path(
    case: dict[str, Any], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    warehouse, scenario = arguments(case)
    output = tmp_path / "out"
    assert main(["run", warehouse, scenario, "--output", str(output)]) == 2
    assert not output.exists()
    error = capsys.readouterr().err
    for field_path in case["paths"]:
        assert f": {field_path}: " in error
    assert case["file"] in error


@pytest.mark.parametrize("case", cases(), ids=lambda case: case["file"])
def test_validate_rejects_invalid_sample(
    case: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    warehouse, scenario = arguments(case)
    assert main(["validate", warehouse, scenario]) == 2
    assert capsys.readouterr().err
