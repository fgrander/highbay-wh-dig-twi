"""Starts Omniverse Kit for tests, and skips them when it is not installed.

Kit does not end after a request to quit (see research.md, "Closing Kit"). A test script therefore
writes its results to a file and ends the process with `os._exit`, using `run_script` from
kit_test_support.py, and every run has an outer time limit.
"""

import contextlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).parents[1]
APP = ROOT / "omniverse" / "highbay.replay.app.kit"
EXTENSIONS = ROOT / "omniverse" / "exts"
BOOTSTRAP = Path(__file__).parent / "omniverse_kit" / "kit_bootstrap.py"
DEFAULT_KIT_DIR = Path(r"C:\dev\omniverse\kit-app-template\_build\windows-x86_64\release")
DEFAULT_TIME_LIMIT_S = 420.0


def kit_directory() -> Path:
    """Returns Kit's folder, or skips the test if Kit is not installed."""
    directory = Path(os.environ.get("HIGHBAY_KIT_DIR", DEFAULT_KIT_DIR))
    if not (directory / "kit" / "kit.exe").is_file():
        pytest.skip(f"Omniverse Kit is not installed in {directory}: run omniverse/setup.ps1")
    return directory


def run_kit_script(
    script: Path,
    arguments: dict[str, Any],
    work_directory: Path,
    settings: list[str] | None = None,
    time_limit_s: float = DEFAULT_TIME_LIMIT_S,
    models: str = "simple",
) -> dict[str, Any]:
    """Runs a script in the windowless application, and returns the results that it wrote.

    Tests use the simple shapes unless they ask for detailed models, which are the default for
    people, so that a test states what it checks.
    """
    directory = kit_directory()
    results_file = work_directory / "kit-results.json"
    arguments_file = work_directory / "kit-arguments.json"
    log_file = work_directory / "kit.log"
    arguments_file.write_text(
        json.dumps({**arguments, "results_file": str(results_file)}), encoding="utf-8"
    )
    command = [
        str(directory / "kit" / "kit.exe"),
        str(APP),
        "--ext-folder",
        str(EXTENSIONS),
        "--ext-folder",
        str(directory / "extscache"),
        "--no-window",
        "--/app/fastShutdown=true",
        f"--/exts/highbay.replay/models={models}",
        *(settings or []),
        "--exec",
        str(BOOTSTRAP),
    ]
    environment = {
        **os.environ,
        "HIGHBAY_KIT_ARGUMENTS": str(arguments_file),
        "HIGHBAY_KIT_SCRIPT": str(script),
    }
    with (
        log_file.open("w", encoding="utf-8", errors="replace") as log,
        contextlib.suppress(subprocess.TimeoutExpired),
    ):
        subprocess.run(
            command,
            stdout=log,
            stderr=subprocess.STDOUT,
            env=environment,
            timeout=time_limit_s,
            check=False,
        )
    if not results_file.is_file():
        tail = log_file.read_text(encoding="utf-8", errors="replace").splitlines()[-40:]
        pytest.fail("Kit wrote no results. End of its log:\n" + "\n".join(tail))
    results: dict[str, Any] = json.loads(results_file.read_text(encoding="utf-8"))
    return results
