"""Loads shown from their definitions, checked inside Kit (FR-010 to FR-013, FR-015)."""

from pathlib import Path
from typing import Any

import pytest

from conftest import SAMPLES
from highbay.replay.core.layout import create_layout
from highbay.replay.core.recorded_source import open_recording
from highbay_sim.cli import main
from kit_runner import run_kit_script

pytestmark = pytest.mark.omniverse

SCRIPT = Path(__file__).parent / "loads_script.py"
DEFAULT_DEFINITIONS = (
    Path(__file__).parents[2] / "omniverse/exts/highbay.replay/data/load_definitions.toml"
)
TOLERANCE_M = 0.01
COLORS = 8
TIMES = [0.0, 3000.0, 6000.0]
DEFINITIONS = """
[types.particle_board]
kind = "board_stack"
length_m = 5.6
width_m = 2.07
smallest_part_m = 1.5
count = 30
thickness_m = 0.019

[types.paper_pallet]
kind = "paper_pallet"
length_m = 5.61
width_m = 2.08
count = 1000
thickness_m = 0.0003
base_thickness_m = 0.03

[types.lost_file]
kind = "file"
file = "does-not-exist.usda"
length_m = 5.6
width_m = 2.07
height_m = 0.6

[loads]
"paper-5610" = [{ type = "paper_pallet" }]
"board-5600" = [{ type = "lost_file" }]
"board-2100-3500" = [
    { type = "particle_board", length_m = 2.1 },
    { type = "particle_board", length_m = 3.5 },
]
"""
# "board-3000-2600" has no definition, and so looks simple.


@pytest.fixture(scope="module")
def run_folder(tmp_path_factory: pytest.TempPathFactory) -> Path:
    folder = tmp_path_factory.mktemp("loads") / "run"
    arguments = [
        "run",
        str(SAMPLES / "replay" / "real-size-warehouse.yaml"),
        str(SAMPLES / "replay" / "real-size-scenario.yaml"),
        "--output",
        str(folder),
        "--replay",
    ]
    assert main(arguments) == 0
    return folder


def expected_prototypes(articles: list[str]) -> dict[str, int]:
    """Returns the prototype of each article: distinct loads follow the colors, in article order."""
    defined = ["paper-5610", "board-5600", "board-2100-3500"]
    next_prototype = COLORS
    prototypes = {}
    for index, article in enumerate(articles):
        if article in defined:
            prototypes[article] = next_prototype
            next_prototype += 1
        else:
            prototypes[article] = index % COLORS
    return prototypes


def find_carried(source: Any) -> list[dict[str, Any]]:
    found: dict[int, dict[str, Any]] = {}
    for time_s in range(int(source.time_range()[1])):
        state = source.state_at(float(time_s))
        for aisle, crane in state.cranes.items():
            if crane.carrying is None or crane.handling is not None:
                continue
            load = source.load(crane.carrying)
            if load is not None and load.article not in found:
                found[load.article] = {
                    "time": float(time_s),
                    "aisle": aisle,
                    "article": load.article,
                }
    return list(found.values())


@pytest.fixture(scope="module")
def results(run_folder: Path, tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    work = tmp_path_factory.mktemp("kit")
    definitions = work / "loads.toml"
    definitions.write_text(DEFINITIONS, encoding="utf-8")
    source = open_recording(run_folder)
    source.state_at(0.0)
    stored = source.stored_load_units()
    articles = source.describe().articles
    keys = {load.article: load.key for load in stored}
    found = run_kit_script(
        SCRIPT,
        {
            "run_folder": str(run_folder),
            "times": TIMES,
            "carried": find_carried(source),
            "details": [
                {"time": 0.0, "key": keys[articles.index(name)]}
                for name in ("paper-5610", "board-2100-3500", "board-3000-2600")
            ],
        },
        work,
        settings=[f"--/exts/highbay.replay/load_definitions={definitions}"],
        models="detailed",
    )
    assert "script_error" not in found, found.get("script_error")
    return found


def test_one_instance_stays_per_cell(results: dict[str, Any]) -> None:
    assert results["instance_count"] == results["cell_count"]


def test_one_prototype_per_definition_and_per_color(results: dict[str, Any]) -> None:
    assert results["prototype_count"] == COLORS + 3


def test_each_stored_load_uses_its_articles_prototype(
    results: dict[str, Any], run_folder: Path
) -> None:
    source = open_recording(run_folder)
    articles = source.describe().articles
    prototypes = expected_prototypes(articles)
    layout = create_layout(source.describe().layout)
    for time_s in TIMES:
        source.state_at(time_s)
        expected = {
            str(layout.cell_instance(load.location)): prototypes[articles[load.article]]
            for load in source.stored_load_units()
        }
        assert results["stored"][str(time_s)] == expected, time_s


def test_a_carried_load_uses_its_articles_prototype(
    results: dict[str, Any], run_folder: Path
) -> None:
    articles = open_recording(run_folder).describe().articles
    prototypes = expected_prototypes(articles)
    assert results["carried"]
    for entry in results["carried"]:
        assert entry["visible"]
        assert entry["prototype"] == prototypes[articles[entry["article"]]]
        assert len(entry["targets"]) == COLORS + 3


def prototype(results: dict[str, Any], run_folder: Path, article: str) -> dict[str, Any]:
    articles = open_recording(run_folder).describe().articles
    return results["prototypes"][str(expected_prototypes(articles)[article])]


def test_a_paper_pallet_shows_as_one_unit_with_its_real_size(
    results: dict[str, Any], run_folder: Path
) -> None:
    shown = prototype(results, run_folder, "paper-5610")
    assert list(shown["children"]) == ["Unit1"]
    low, high = shown["bounds"]["min"], shown["bounds"]["max"]
    assert high[0] - low[0] == pytest.approx(5.61, abs=TOLERANCE_M)
    assert high[2] - low[2] == pytest.approx(2.08, abs=TOLERANCE_M)
    assert high[1] - low[1] == pytest.approx(0.33, abs=TOLERANCE_M)
    assert (low[0] + high[0]) / 2 == pytest.approx(0.0, abs=TOLERANCE_M)
    # It starts at the top of the forks, 0.1125 m above the floor of a cell 1.5 m high.
    assert low[1] == pytest.approx(0.1125 - 0.75, abs=TOLERANCE_M)


def test_the_parts_of_a_split_stack_keep_their_lengths_and_sides(
    results: dict[str, Any], run_folder: Path
) -> None:
    shown = prototype(results, run_folder, "board-2100-3500")
    assert sorted(shown["children"]) == ["Unit1", "Unit2"]
    first = shown["children"]["Unit1"]["bounds"]
    second = shown["children"]["Unit2"]["bounds"]
    assert first["max"][0] - first["min"][0] == pytest.approx(2.1, abs=TOLERANCE_M)
    assert second["max"][0] - second["min"][0] == pytest.approx(3.5, abs=TOLERANCE_M)
    # 5.61 m in all, with a cut of 1 cm between them at -2.805 + 2.1 = -0.705 m.
    assert first["min"][0] == pytest.approx(-2.805, abs=TOLERANCE_M)
    assert first["max"][0] == pytest.approx(-0.705, abs=TOLERANCE_M)
    assert second["max"][0] == pytest.approx(2.805, abs=TOLERANCE_M)


def test_sheets_keep_their_two_materials(results: dict[str, Any]) -> None:
    assert results["sheet_material"]
    assert results["sheet_material"].endswith("/Materials/SheetLight")


def test_what_cannot_be_used_opens_with_warnings_in_the_window(results: dict[str, Any]) -> None:
    assert results["message"] == ""
    text = "\n".join(results["warnings"])
    assert "board-3000-2600" in text  # No definition
    assert "does-not-exist.usda" in text  # A file that cannot be loaded


def test_a_lost_file_falls_back_to_a_simple_shape(
    results: dict[str, Any], run_folder: Path
) -> None:
    shown = prototype(results, run_folder, "board-5600")
    assert shown["children"]["Unit1"]["type"] == "Cube"


def test_details_say_what_a_load_is(results: dict[str, Any], run_folder: Path) -> None:
    source = open_recording(run_folder)
    source.state_at(0.0)
    articles = source.describe().articles
    keys = {articles[load.article]: load.key for load in source.stored_load_units()}
    assert "Load: paper_pallet" in results["details"][keys["paper-5610"]]
    expected = "Load: particle_board 2.1 m + particle_board 3.5 m"
    assert expected in results["details"][keys["board-2100-3500"]]
    assert not any(line.startswith("Load:") for line in results["details"][keys["board-3000-2600"]])


@pytest.mark.parametrize(
    ("warehouse", "scenario"),
    [
        ("small-warehouse.yaml", "daily-scenario.yaml"),
        ("replay/real-size-warehouse.yaml", "replay/real-size-scenario.yaml"),
    ],
)
def test_samples_with_the_default_definitions_have_no_warnings(
    tmp_path: Path, warehouse: str, scenario: str
) -> None:
    folder = tmp_path / "run"
    arguments = [
        "run",
        str(SAMPLES / warehouse),
        str(SAMPLES / scenario),
        "--output",
        str(folder),
        "--replay",
    ]
    assert main(arguments) == 0
    found = run_kit_script(
        SCRIPT,
        {"run_folder": str(folder), "times": [0.0], "carried": [], "details": []},
        tmp_path,
        models="detailed",
    )
    assert "script_error" not in found, found.get("script_error")
    assert found["warnings"] == []
    assert DEFAULT_DEFINITIONS.is_file()
