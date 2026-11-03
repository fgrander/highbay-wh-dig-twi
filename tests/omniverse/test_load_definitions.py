"""Reading and checking load definitions, with values worked out by hand.

Cells are 5.8 m long, 1.5 m high, and 2.3 m wide. A load starts (1 - 0.85) / 2 * 1.5 = 0.1125 m
above a cell's floor, which leaves 1.3875 m of height.
"""

from pathlib import Path

import pytest

from highbay.replay.core.layout import create_layout
from highbay.replay.core.load_definitions import (
    LoadDefinitions,
    read_load_definitions,
    resolve_loads,
)

LAYOUT = create_layout(
    {
        "aisle_count": 1,
        "racks_per_aisle": 2,
        "bays_per_rack": 5,
        "levels_per_rack": 3,
        "cell": {"height_m": 1.5, "length_m": 5.8, "width_m": 2.3},
    }
)
TYPES = """
[types.board]
kind = "board_stack"
length_m = 5.6
width_m = 2.07
smallest_part_m = 1.5
count = 30
thickness_m = 0.019

[types.paper]
kind = "paper_pallet"
length_m = 5.61
width_m = 2.08
count = 1000
thickness_m = 0.0003
base_thickness_m = 0.03
"""


def read(tmp_path: Path, text: str) -> LoadDefinitions:
    path = tmp_path / "loads.toml"
    path.write_text(text, encoding="utf-8")
    return read_load_definitions(path)


def resolve(tmp_path: Path, loads: str, articles: list[str]):  # type: ignore[no-untyped-def]
    definitions = read(tmp_path, TYPES + "\n[loads]\n" + loads)
    assert definitions.warnings == []
    return resolve_loads(definitions, articles, LAYOUT)


def test_a_good_file_gives_types_with_their_heights(tmp_path: Path) -> None:
    definitions = read(tmp_path, TYPES)
    assert definitions.warnings == []
    assert definitions.types["board"].height_m == pytest.approx(0.57)  # 30 * 19 mm
    assert definitions.types["paper"].height_m == pytest.approx(0.33)  # 1000 * 0.3 mm + 30 mm


def test_a_whole_unit_is_centered(tmp_path: Path) -> None:
    (load,), warnings = resolve(tmp_path, '"p" = [{ type = "paper" }]', ["p"])
    assert warnings == []
    assert len(load.units) == 1
    assert load.units[0].center_x == 0.0
    assert load.units[0].length_m == 5.61
    assert load.label == "paper"
    assert load.size == pytest.approx((5.61, 0.33, 2.08))


def test_two_parts_lie_end_to_end_with_their_cut_where_their_lengths_put_it(tmp_path: Path) -> None:
    text = '"b" = [{ type = "board", length_m = 2.1 }, { type = "board", length_m = 3.5 }]'
    (load,), warnings = resolve(tmp_path, text, ["b"])
    assert warnings == []
    first, second = load.units
    # 2.1 + 0.01 + 3.5 = 5.61 m in all, from -2.805 to 2.805.
    assert first.center_x == pytest.approx(-2.805 + 1.05)
    assert second.center_x == pytest.approx(2.805 - 1.75)
    assert load.label == "board 2.1 m + board 3.5 m"
    assert load.size == pytest.approx((5.61, 0.57, 2.07))


def test_the_same_definition_gives_the_same_load(tmp_path: Path) -> None:
    text = '"a" = [{ type = "paper" }]\n"b" = [{ type = "paper" }]'
    (first, second), _ = resolve(tmp_path, text, ["a", "b"])
    assert first == second
    assert hash(first) == hash(second)


def test_a_file_that_does_not_exist_gives_a_warning_and_no_definitions(tmp_path: Path) -> None:
    path = tmp_path / "missing.toml"
    definitions = read_load_definitions(path)
    assert definitions.types == {}
    assert len(definitions.warnings) == 1
    assert str(path) in definitions.warnings[0]


def test_a_file_that_is_not_toml_gives_a_warning_and_no_definitions(tmp_path: Path) -> None:
    definitions = read(tmp_path, "[types.board\nkind")
    assert definitions.types == {}
    assert "loads.toml" in definitions.warnings[0]


@pytest.mark.parametrize(
    ("line", "named"),
    [
        ('kind = "unknown"', "kind"),
        ("length_m = 0", "length_m"),
        ('length_m = "long"', "length_m"),
        ("width_m = -1.0", "width_m"),
        ("count = 0", "count"),
        ("count = 1.5", "count"),
        ("thickness_m = 0", "thickness_m"),
        ("smallest_part_m = 0", "smallest_part_m"),
        ('color = "red"', "color"),
    ],
)
def test_each_rule_for_a_type_gives_a_warning_naming_the_type_and_field(
    tmp_path: Path, line: str, named: str
) -> None:
    base = {
        "kind": '"board_stack"',
        "length_m": "5.6",
        "width_m": "2.07",
        "count": "30",
        "thickness_m": "0.019",
    }
    key = line.split(" = ")[0]
    base[key] = line.split(" = ")[1]
    text = "[types.broken]\n" + "\n".join(f"{name} = {value}" for name, value in base.items())
    definitions = read(tmp_path, text)
    assert "broken" not in definitions.types
    assert len(definitions.warnings) == 1
    assert "broken" in definitions.warnings[0]
    assert named in definitions.warnings[0]


def test_a_paper_pallet_needs_its_base(tmp_path: Path) -> None:
    text = TYPES.replace("base_thickness_m = 0.03\n", "")
    definitions = read(tmp_path, text)
    assert "paper" not in definitions.types
    assert "base_thickness_m" in definitions.warnings[0]


def test_a_relative_file_starts_at_the_definitions_folder(tmp_path: Path) -> None:
    text = """
[types.scan]
kind = "file"
file = "looks/stack.usd"
length_m = 5.6
width_m = 2.07
height_m = 0.6
"""
    definitions = read(tmp_path, text)
    assert definitions.warnings == []
    assert definitions.types["scan"].file == str(tmp_path / "looks" / "stack.usd")
    assert definitions.types["scan"].height_m == 0.6


def test_an_article_with_no_definition_gives_a_warning_and_no_load(tmp_path: Path) -> None:
    (load,), warnings = resolve(tmp_path, "", ["unknown-article"])
    assert load is None
    assert len(warnings) == 1
    assert "unknown-article" in warnings[0]


def test_a_definition_for_an_article_not_in_the_run_gives_no_warning(tmp_path: Path) -> None:
    (load,), warnings = resolve(
        tmp_path, '"elsewhere" = [{ type = "paper" }]\n"p" = [{ type = "paper" }]', ["p"]
    )
    assert load is not None
    assert warnings == []


def test_an_unknown_type_gives_a_simple_unit_and_a_warning(tmp_path: Path) -> None:
    (load,), warnings = resolve(tmp_path, '"p" = [{ type = "nothing" }]', ["p"])
    assert load.units[0].unit_type is None
    assert load.units[0].size == pytest.approx(LAYOUT.load_size())
    assert len(warnings) == 1
    assert "p" in warnings[0]
    assert "nothing" in warnings[0]


@pytest.mark.parametrize("text", ['"p" = []', '"p" = "paper"', '"p" = [{ length_m = 2.0 }]'])
def test_a_definition_of_the_wrong_form_counts_as_no_definition(tmp_path: Path, text: str) -> None:
    (load,), warnings = resolve(tmp_path, text, ["p"])
    assert load is None
    assert "p" in warnings[0]


def test_more_than_two_units_count_as_no_definition(tmp_path: Path) -> None:
    text = '"p" = [{ type = "paper" }, { type = "paper" }, { type = "paper" }]'
    (load,), warnings = resolve(tmp_path, text, ["p"])
    assert load is None
    assert "p" in warnings[0]


@pytest.mark.parametrize(
    ("first", "second", "named"),
    [
        (2.0, 3.0, "5.6"),  # They add up to 5 m.
        (1.0, 4.6, "1"),  # The first is below 1.5 m.
    ],
)
def test_a_split_against_its_type_shows_as_defined_with_a_warning(
    tmp_path: Path, first: float, second: float, named: str
) -> None:
    parts = f'{{ type = "board", length_m = {first} }}, {{ type = "board", length_m = {second} }}'
    text = f'"b" = [{parts}]'
    (load,), warnings = resolve(tmp_path, text, ["b"])
    assert [unit.length_m for unit in load.units] == [first, second]
    assert len(warnings) == 1
    assert "b" in warnings[0]
    assert named in warnings[0]


def test_a_type_with_no_smallest_part_cannot_be_split(tmp_path: Path) -> None:
    text = '"p" = [{ type = "paper", length_m = 2.8 }, { type = "paper", length_m = 2.81 }]'
    (_load,), warnings = resolve(tmp_path, text, ["p"])
    assert len(warnings) == 1
    assert "split" in warnings[0]


def test_a_split_needs_the_length_of_both_parts(tmp_path: Path) -> None:
    text = '"b" = [{ type = "board" }, { type = "board", length_m = 3.5 }]'
    (load,), warnings = resolve(tmp_path, text, ["b"])
    assert load.units[0].length_m > 0
    assert "length" in warnings[0]


def test_a_load_that_does_not_fit_shows_as_defined_with_its_size_named(tmp_path: Path) -> None:
    narrow = create_layout(
        {
            "aisle_count": 1,
            "racks_per_aisle": 2,
            "bays_per_rack": 5,
            "levels_per_rack": 3,
            "cell": {"height_m": 0.5, "length_m": 3.2, "width_m": 1.5},
        }
    )
    definitions = read(tmp_path, TYPES + '\n[loads]\n"p" = [{ type = "paper" }]')
    (load,), warnings = resolve_loads(definitions, ["p"], narrow)
    assert load is not None
    assert len(warnings) == 1
    assert "p" in warnings[0]
    assert "5.61" in warnings[0]


def test_each_warning_occurs_once(tmp_path: Path) -> None:
    _, warnings = resolve(
        tmp_path, '"a" = [{ type = "nothing" }]\n"b" = [{ type = "nothing" }]', ["a", "a"]
    )
    assert len(warnings) == len(set(warnings))
