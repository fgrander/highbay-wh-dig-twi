"""FR-013 and SC-006: runs with no PLC need no connection library, and nothing about them changes.

Together with test_reference_results.py and test_stepped_hand_calculated.py, whose reference values
stay as they are, this shows that results without a PLC are unchanged.
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[2]
WAREHOUSE = str(ROOT / "samples" / "verification" / "v1-warehouse.yaml")
SCENARIO = str(ROOT / "tests" / "data" / "plc-scenario.yaml")
WITH_LIBRARY_BLOCKED = """
import sys
sys.modules["s7commplus"] = None
from highbay_sim.cli import main
code = main(sys.argv[1:])
assert "highbay_sim.plc.s7_link" not in sys.modules
assert sys.modules["s7commplus"] is None
sys.exit(code)
"""


def run_blocked(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", WITH_LIBRARY_BLOCKED, *arguments],
        capture_output=True,
        text=True,
        check=False,
    )


def test_validate_needs_no_library() -> None:
    result = run_blocked("validate", WAREHOUSE, SCENARIO)
    assert result.returncode == 0, result.stderr


def test_an_event_based_run_needs_no_library(tmp_path: Path) -> None:
    result = run_blocked("run", WAREHOUSE, SCENARIO, "--output", str(tmp_path))
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "result.json").is_file()


def test_a_time_stepped_run_needs_no_library_and_has_no_plc_section(tmp_path: Path) -> None:
    result = run_blocked("run", WAREHOUSE, SCENARIO, "--output", str(tmp_path), "--time-stepped")
    assert result.returncode == 0, result.stderr
    document = json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))
    assert "plc" not in document
    assert "PLC" not in (tmp_path / "report.md").read_text(encoding="utf-8")


def test_asking_for_a_plc_without_the_library_says_how_to_install_it(tmp_path: Path) -> None:
    script = WITH_LIBRARY_BLOCKED.replace(
        'assert "highbay_sim.plc.s7_link" not in sys.modules\n', ""
    )
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            "run",
            WAREHOUSE,
            SCENARIO,
            "--output",
            str(tmp_path),
            "--time-stepped",
            "--plc-host",
            "plc.example",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "uv sync --extra plc" in result.stderr
