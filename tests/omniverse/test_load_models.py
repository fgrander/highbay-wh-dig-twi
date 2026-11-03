"""The generated load units' text. Whether USD reads it as intended is checked in Kit."""

import re

import pytest

from highbay.replay.core.load_definitions import LoadUnitType
from highbay.replay.core.load_models import board_stack_usda, paper_pallet_usda

BOARD = LoadUnitType(
    "board",
    "board_stack",
    length_m=5.6,
    width_m=2.07,
    height_m=0.57,
    smallest_part_m=1.5,
    count=30,
    thickness_m=0.019,
)
PAPER = LoadUnitType(
    "paper",
    "paper_pallet",
    length_m=5.61,
    width_m=2.08,
    height_m=0.33,
    count=1000,
    thickness_m=0.0003,
    base_thickness_m=0.03,
)


def points(text: str, mesh: str) -> list[tuple[float, float, float]]:
    block = text[text.index(f'def Mesh "{mesh}"') :]
    found = re.search(r"points = \[(.*?)\]", block, re.DOTALL)
    assert found
    return [
        (float(x), float(y), float(z))
        for x, y, z in re.findall(r"\(([^,]+), ([^,]+), ([^)]+)\)", found.group(1))
    ]


def face_count(text: str, mesh: str) -> int:
    block = text[text.index(f'def Mesh "{mesh}"') :]
    found = re.search(r"faceVertexCounts = \[(.*?)\]", block, re.DOTALL)
    assert found
    return len(found.group(1).split(","))


def subset(text: str, name: str) -> list[int]:
    block = text[text.index(f'def GeomSubset "{name}"') :]
    found = re.search(r"indices = \[(.*?)\]", block, re.DOTALL)
    assert found
    return [int(value) for value in found.group(1).split(",")]


@pytest.mark.parametrize(("build", "unit"), [(board_stack_usda, BOARD), (paper_pallet_usda, PAPER)])
def test_text_is_a_balanced_usda_with_its_default_prim(build, unit) -> None:  # type: ignore[no-untyped-def]
    text = build(unit, unit.length_m)
    assert text.startswith("#usda 1.0")
    assert 'defaultPrim = "Look"' in text
    assert text.count("{") == text.count("}")
    assert build(unit, unit.length_m) == text


def test_a_board_stack_has_one_box_per_board() -> None:
    text = board_stack_usda(BOARD, 5.6)
    assert face_count(text, "Boards") == 30 * 6
    assert len(points(text, "Boards")) == 30 * 8


@pytest.mark.parametrize("length", [5.6, 2.1, 1.5])
def test_a_board_stack_has_its_size_with_its_origin_on_the_floor_at_the_center(
    length: float,
) -> None:
    found = points(board_stack_usda(BOARD, length), "Boards")
    assert min(point[1] for point in found) == pytest.approx(0.0)
    assert max(point[1] for point in found) == pytest.approx(0.57, abs=0.001)
    assert min(point[0] for point in found) == pytest.approx(-length / 2)
    assert max(point[0] for point in found) == pytest.approx(length / 2)
    assert min(point[2] for point in found) == pytest.approx(-2.07 / 2)
    assert max(point[2] for point in found) == pytest.approx(2.07 / 2)


def test_every_board_can_be_seen_by_every_second_one_lying_slightly_inward() -> None:
    found = points(board_stack_usda(BOARD, 5.6), "Boards")
    first_board = {point[0] for point in found[:8]}
    second_board = {point[0] for point in found[8:16]}
    assert first_board != second_board


def test_paper_lies_on_one_board_30_mm_thick() -> None:
    text = paper_pallet_usda(PAPER, 5.61)
    base = points(text, "Base")
    sheets = points(text, "Sheets")
    assert face_count(text, "Base") == 6  # One box
    assert min(point[1] for point in base) == pytest.approx(0.0)
    assert max(point[1] for point in base) == pytest.approx(0.03, abs=0.001)
    assert min(point[1] for point in sheets) == pytest.approx(0.03, abs=0.001)
    assert max(point[1] for point in sheets) == pytest.approx(0.33, abs=0.001)


def test_a_paper_pallet_has_its_size_with_its_origin_at_the_center() -> None:
    text = paper_pallet_usda(PAPER, 5.61)
    for mesh in ("Base", "Sheets"):
        found = points(text, mesh)
        assert min(point[0] for point in found) == pytest.approx(-5.61 / 2)
        assert max(point[0] for point in found) == pytest.approx(5.61 / 2)
        assert min(point[2] for point in found) == pytest.approx(-2.08 / 2)
        assert max(point[2] for point in found) == pytest.approx(2.08 / 2)


def test_the_two_subsets_of_the_sheets_cover_each_face_once() -> None:
    text = paper_pallet_usda(PAPER, 5.61)
    faces = sorted(subset(text, "LightBands") + subset(text, "DarkBands"))
    assert faces == list(range(face_count(text, "Sheets")))
    assert subset(text, "LightBands")
    assert subset(text, "DarkBands")


def test_a_color_in_the_type_reaches_the_material() -> None:
    colored = LoadUnitType(
        "board",
        "board_stack",
        length_m=5.6,
        width_m=2.07,
        height_m=0.57,
        count=30,
        thickness_m=0.019,
        color="#ff0000",
    )
    assert board_stack_usda(colored, 5.6) != board_stack_usda(BOARD, 5.6)
    assert "(1, 0, 0)" in board_stack_usda(colored, 5.6)
