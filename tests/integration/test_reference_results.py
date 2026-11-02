"""SC-009: event-based results stay as they were before the time-stepped mode was added.

tests/data/reference_results.json was written with this file's main block on the code of version
0.2.0. Do not write it again to make a failure pass, as changed results must be named as such.
Version and input hashes are taken out before hashing: the version changes on purpose, and input
hashes depend on the line endings of the checkout.
"""

import hashlib
import json
import tempfile
from pathlib import Path

from highbay_sim import __version__
from highbay_sim.cli import main

SAMPLES = Path(__file__).parents[2] / "samples"
REFERENCE_FILE = Path(__file__).parents[1] / "data" / "reference_results.json"
OUTPUTS = ("orders.csv", "report.md", "result.json", "replay.json")
SAMPLE_PAIRS = (
    ("small-warehouse.yaml", "daily-scenario.yaml"),
    ("replay/overloaded-warehouse.yaml", "replay/busy-scenario.yaml"),
    ("verification/v1-warehouse.yaml", "verification/v1-scenario.yaml"),
    ("verification/v1-warehouse.yaml", "verification/v3-scenario.yaml"),
    ("verification/v2-warehouse.yaml", "verification/v2-scenario.yaml"),
)


def normalized_hash(text: str, input_hashes: tuple[str, str]) -> str:
    text = text.replace(__version__, "<version>")
    for input_hash in input_hashes:
        text = text.replace(input_hash, "<input hash>")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def current_hashes() -> dict[str, dict[str, str]]:
    hashes = {}
    for warehouse, scenario in SAMPLE_PAIRS:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            arguments = [str(SAMPLES / warehouse), str(SAMPLES / scenario)]
            assert main(["run", *arguments, "--output", str(output), "--replay"]) == 0
            run = json.loads((output / "result.json").read_text(encoding="utf-8"))["run"]
            input_hashes = (run["warehouse"]["sha256"], run["scenario"]["sha256"])
            hashes[f"{warehouse} {scenario}"] = {
                name: normalized_hash((output / name).read_text(encoding="utf-8"), input_hashes)
                for name in OUTPUTS
            }
    return hashes


def test_event_based_results_are_unchanged() -> None:
    assert current_hashes() == json.loads(REFERENCE_FILE.read_text(encoding="utf-8"))


if __name__ == "__main__":
    REFERENCE_FILE.parent.mkdir(exist_ok=True)
    REFERENCE_FILE.write_text(
        json.dumps(current_hashes(), indent=2) + "\n", encoding="utf-8", newline="\n"
    )
