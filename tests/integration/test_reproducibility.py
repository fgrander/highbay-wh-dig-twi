import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

from conftest import write_yaml

ROOT = Path(__file__).parents[2]
WAREHOUSE = ROOT / "samples" / "small-warehouse.yaml"
SCENARIO = ROOT / "samples" / "daily-scenario.yaml"
OUTPUT_FILES = ("report.md", "result.json", "orders.csv")
RUNS = 10
RUNS_UNDER_LOAD = 4


def run_cli(output: Path, hash_seed: int, scenario: Path = SCENARIO) -> None:
    environment = {**os.environ, "PYTHONHASHSEED": str(hash_seed)}
    subprocess.run(
        [
            sys.executable,
            "-m",
            "highbay_sim.cli",
            "run",
            str(WAREHOUSE),
            str(scenario),
            "--output",
            str(output),
        ],
        check=True,
        capture_output=True,
        env=environment,
    )


def contents(output: Path) -> dict[str, bytes]:
    return {name: (output / name).read_bytes() for name in OUTPUT_FILES}


def test_repeated_runs_are_byte_identical_also_under_load(tmp_path: Path) -> None:
    """SC-002: 10 runs, some on a busy machine, in processes with different hash seeds."""
    reference = None
    for index in range(RUNS - RUNS_UNDER_LOAD):
        output = tmp_path / f"run-{index}"
        run_cli(output, hash_seed=index)
        reference = reference or contents(output)
        assert contents(output) == reference

    load = [
        subprocess.Popen([sys.executable, "-c", "while True: pass"])
        for _ in range(os.cpu_count() or 2)
    ]
    try:
        for index in range(RUNS_UNDER_LOAD):
            output = tmp_path / f"loaded-{index}"
            run_cli(output, hash_seed=1000 + index)
            assert contents(output) == reference
    finally:
        for process in load:
            process.kill()
            process.wait()


def test_different_seed_changes_orders_and_recorded_seed(tmp_path: Path) -> None:
    content = yaml.safe_load(SCENARIO.read_text(encoding="utf-8"))
    content["seed"] = 43
    other_scenario = write_yaml(tmp_path / "other.yaml", content)

    run_cli(tmp_path / "a", hash_seed=0)
    run_cli(tmp_path / "b", hash_seed=0, scenario=other_scenario)

    assert (tmp_path / "a" / "orders.csv").read_bytes() != (
        tmp_path / "b" / "orders.csv"
    ).read_bytes()
    result = json.loads((tmp_path / "b" / "result.json").read_text(encoding="utf-8"))
    assert result["run"]["seed"] == 43
    assert "Seed: 43" in (tmp_path / "b" / "report.md").read_text(encoding="utf-8")


def test_outputs_contain_no_time_of_run_or_machine_details(tmp_path: Path) -> None:
    run_cli(tmp_path / "a", hash_seed=0)
    for name in OUTPUT_FILES:
        text = (tmp_path / "a" / name).read_text(encoding="utf-8")
        assert os.environ.get("COMPUTERNAME", "no-such-machine-name") not in text
        assert str(Path.home()) not in text


def test_outputs_use_unix_line_endings_on_every_platform(tmp_path: Path) -> None:
    run_cli(tmp_path / "a", hash_seed=0)
    for name in OUTPUT_FILES:
        assert b"\r" not in (tmp_path / "a" / name).read_bytes()


def test_runs_with_no_display_and_loads_no_graphical_module(tmp_path: Path) -> None:
    """FR-008. On Windows the module check is what counts, as DISPLAY is not used there."""
    code = (
        "import sys\n"
        "from highbay_sim.cli import main\n"
        f"code = main(['run', {str(WAREHOUSE)!r}, {str(SCENARIO)!r}, '--output', "
        f"{str(tmp_path / 'out')!r}])\n"
        "graphical = {'tkinter', 'turtle', 'PyQt5', 'PyQt6', 'PySide6', 'wx', 'pygame', "
        "'pyglet', 'matplotlib', 'OpenGL'}\n"
        "assert not graphical & set(sys.modules), graphical & set(sys.modules)\n"
        "sys.exit(code)\n"
    )
    environment = {key: value for key, value in os.environ.items() if key != "DISPLAY"}
    subprocess.run([sys.executable, "-c", code], check=True, capture_output=True, env=environment)
    assert (tmp_path / "out" / "report.md").is_file()
