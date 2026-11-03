"""The generated crane text. Whether USD reads it as intended is checked in Kit."""

import re

import pytest

from highbay.replay.core.crane_dimensions import crane_dimensions
from highbay.replay.core.crane_model import crane_carriage_usda, crane_mast_usda
from highbay.replay.core.layout import create_layout

SMALL = create_layout(
    {
        "aisle_count": 1,
        "racks_per_aisle": 2,
        "bays_per_rack": 5,
        "levels_per_rack": 3,
        "cell": {"height_m": 1.5, "length_m": 3.2, "width_m": 1.5},
    }
)
TALL = create_layout(
    {
        "aisle_count": 1,
        "racks_per_aisle": 2,
        "bays_per_rack": 5,
        "levels_per_rack": 20,
        "cell": {"height_m": 2.0, "length_m": 4.0, "width_m": 1.2},
    }
)


def prim(text: str, name: str) -> str:
    start = text.index(f'"{name}"')
    return text[start : text.index("\n    }", start)]


def translate(text: str, name: str) -> list[float]:
    match = re.search(r"xformOp:translate = \(([^)]*)\)", prim(text, name))
    assert match, name
    return [float(value) for value in match.group(1).split(",")]


def scale(text: str, name: str) -> list[float]:
    match = re.search(r"xformOp:scale = \(([^)]*)\)", prim(text, name))
    assert match, name
    return [float(value) for value in match.group(1).split(",")]


@pytest.mark.parametrize("build", [crane_mast_usda, crane_carriage_usda])
def test_text_is_a_balanced_usda_with_its_default_prim(build) -> None:  # type: ignore[no-untyped-def]
    text = build(SMALL)
    assert text.startswith("#usda 1.0")
    assert 'defaultPrim = "Look"' in text
    assert text.count("{") == text.count("}")
    assert text.count("(") == text.count(")")


@pytest.mark.parametrize("build", [crane_mast_usda, crane_carriage_usda])
def test_identical_warehouses_give_identical_text(build) -> None:  # type: ignore[no-untyped-def]
    assert build(SMALL) == build(SMALL)
    assert build(SMALL) != build(TALL)


def test_mast_has_the_parts_of_a_two_column_crane() -> None:
    text = crane_mast_usda(SMALL)
    for name in (
        "ColumnLeft",
        "ColumnRight",
        "BogieLeft",
        "BogieRight",
        "TopBeam",
        "FloorTie",
        "Cabinet",
    ):
        assert f'"{name}"' in text


def test_carriage_has_two_sections_with_three_stages_each() -> None:
    text = crane_carriage_usda(SMALL)
    for section in ("Section1", "Section2"):
        assert f'def Xform "{section}"' in text
    assert text.count('def Xform "Base"') == 2
    assert text.count('def Xform "Middle"') == 2
    assert text.count('def Xform "Top"') == 2


@pytest.mark.parametrize("layout", [SMALL, TALL])
def test_columns_follow_the_dimensions(layout) -> None:  # type: ignore[no-untyped-def]
    size = crane_dimensions(layout)
    text = crane_mast_usda(layout)
    assert translate(text, "ColumnLeft")[0] == pytest.approx(-size.column_x, abs=1e-3)
    assert translate(text, "ColumnRight")[0] == pytest.approx(size.column_x, abs=1e-3)
    # The file's origin is at half the height, as for the simple shape that it replaces.
    column_top = translate(text, "ColumnLeft")[1] + scale(text, "ColumnLeft")[1] / 2
    beam_bottom = translate(text, "TopBeam")[1] - scale(text, "TopBeam")[1] / 2
    assert column_top == pytest.approx(beam_bottom, abs=1e-3)
    beam_top = translate(text, "TopBeam")[1] + scale(text, "TopBeam")[1] / 2
    assert beam_top == pytest.approx(size.height / 2, abs=1e-3)


@pytest.mark.parametrize("layout", [SMALL, TALL])
def test_forks_follow_the_dimensions(layout) -> None:  # type: ignore[no-untyped-def]
    size = crane_dimensions(layout)
    text = crane_carriage_usda(layout)
    section = text[text.index('"Section1"') :]
    bottom = translate(section, "TineA")[1] - scale(section, "TineA")[1] / 2
    top = translate(section, "TineA")[1] + scale(section, "TineA")[1] / 2
    assert bottom == pytest.approx(size.fork_bottom, abs=1e-3)
    assert top == pytest.approx(size.fork_top, abs=1e-3)
    assert scale(section, "TineA")[2] == pytest.approx(size.fork_length, abs=1e-3)


def test_columns_and_end_frames_have_no_material_so_they_show_the_activity() -> None:
    assert "material:binding" not in prim(crane_mast_usda(SMALL), "ColumnLeft")
    assert "material:binding" not in prim(crane_mast_usda(SMALL), "ColumnRight")
    assert "material:binding" not in prim(crane_carriage_usda(SMALL), "EndFrameLeft")
    assert "material:binding" not in prim(crane_carriage_usda(SMALL), "EndFrameRight")
    assert "material:binding" in prim(crane_mast_usda(SMALL), "BogieLeft")
