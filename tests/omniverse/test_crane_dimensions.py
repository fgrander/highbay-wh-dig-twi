"""The sizes of a two-column crane, with values worked out by hand.

The sample warehouse's cell is 3.2 m long, 1.5 m high, and 1.5 m wide, in 10 levels.
"""

import pytest

from highbay.replay.core.crane_dimensions import (
    FLOOR_TIE_HEIGHT_M,
    MINIMUM_FORK_THICKNESS_M,
    crane_boxes,
    crane_dimensions,
)
from highbay.replay.core.layout import RACK_MEMBER_THICKNESS_M, Box, create_layout

SAMPLE = create_layout(
    {
        "aisle_count": 2,
        "racks_per_aisle": 2,
        "bays_per_rack": 40,
        "levels_per_rack": 10,
        "cell": {"height_m": 1.5, "length_m": 3.2, "width_m": 1.5},
    }
)
LOW_CELLS = create_layout(
    {
        "aisle_count": 1,
        "racks_per_aisle": 2,
        "bays_per_rack": 5,
        "levels_per_rack": 3,
        "cell": {"height_m": 0.5, "length_m": 3.2, "width_m": 1.5},
    }
)
SIZE = crane_dimensions(SAMPLE)


def low(box: Box, axis: int) -> float:
    return box.center[axis] - box.size[axis] / 2


def high(box: Box, axis: int) -> float:
    return box.center[axis] + box.size[axis] / 2


def overlap(first: Box, second: Box) -> bool:
    return all(
        low(first, axis) < high(second, axis) and low(second, axis) < high(first, axis)
        for axis in range(3)
    )


def boxes(
    extension: float = 0.0, load_offset: float = 0.0, carrying: bool = False
) -> dict[str, Box]:
    return crane_boxes(SAMPLE, SIZE, 1, (20.0, 0.0), extension, load_offset, carrying)


def test_sizes_follow_the_warehouse() -> None:
    # Half of a cell, the clearance of 0.25 m, and half of a column of 0.34 m.
    assert SIZE.column_x == pytest.approx(1.6 + 0.25 + 0.17)
    assert SIZE.section_x == pytest.approx(0.8)  # The center of each half of a cell
    assert SIZE.reach == pytest.approx(1.5)  # (aisle 1.5 + cell 1.5) / 2
    assert SIZE.height == pytest.approx(15.0)


def test_forks_lie_between_the_rack_beam_and_the_load() -> None:
    assert SIZE.fork_top == pytest.approx(0.1125)  # (1 - 0.85) / 2 of 1.5 m
    assert SIZE.fork_bottom == pytest.approx(RACK_MEMBER_THICKNESS_M / 2 + 0.005)


def test_low_cells_give_thin_forks_rather_than_an_error() -> None:
    low_size = crane_dimensions(LOW_CELLS)
    assert low_size.fork_top == pytest.approx(0.0375)
    assert low_size.fork_top - low_size.fork_bottom == pytest.approx(MINIMUM_FORK_THICKNESS_M)


def test_the_boxes_name_the_parts_of_a_crane() -> None:
    assert {
        "ColumnLeft",
        "ColumnRight",
        "TravelGearLeft",
        "TravelGearRight",
        "TopBeam",
        "FloorTie",
        "Cabinet",
        "Ladder",
        "EndFrameLeft",
        "EndFrameRight",
        "Plate",
        "Section1",
        "Section2",
    } <= set(boxes())
    assert "Load" not in boxes()
    assert "Load" in boxes(carrying=True)


def test_boxes_stand_at_the_cranes_position() -> None:
    found = boxes()
    assert found["ColumnLeft"].center[0] == pytest.approx(20.0 - SIZE.column_x)
    assert found["ColumnRight"].center[0] == pytest.approx(20.0 + SIZE.column_x)
    assert low(found["TravelGearLeft"], 1) == pytest.approx(0.0)
    assert high(found["TopBeam"], 1) >= SIZE.height


def test_carriage_parts_follow_the_lift_position_and_columns_do_not() -> None:
    raised = crane_boxes(SAMPLE, SIZE, 1, (20.0, 6.0))
    assert raised["EndFrameLeft"].center[1] == pytest.approx(
        boxes()["EndFrameLeft"].center[1] + 6.0
    )
    assert raised["Section1"].center[1] == pytest.approx(boxes()["Section1"].center[1] + 6.0)
    assert raised["ColumnLeft"] == boxes()["ColumnLeft"]


def test_forks_reach_out_as_far_as_they_extend() -> None:
    rest = boxes()["Section1"]
    out = boxes(extension=-1.5)["Section1"]
    assert low(out, 2) == pytest.approx(low(rest, 2) - 1.5)
    assert high(out, 2) == pytest.approx(high(rest, 2))  # The base stage stays in the crane.


def test_load_stands_at_its_offset_at_the_height_of_a_stored_one() -> None:
    load = boxes(load_offset=1.5, carrying=True)["Load"]
    stored = SAMPLE.cell_box((1, 2, 7, 1))
    assert load.center[2] == pytest.approx(1.5)
    assert load.center[1] == pytest.approx(stored.center[1])
    assert load.size == pytest.approx(SAMPLE.load_size())


def test_forks_and_load_clear_the_rack_at_the_lowest_level() -> None:
    half = SAMPLE.cell_width / 2
    for extension, rack in ((-SIZE.reach, 1), (SIZE.reach, 2)):
        found = boxes(extension=extension, load_offset=extension, carrying=True)
        for beam_z in (SAMPLE.rack_z(1, rack) - half, SAMPLE.rack_z(1, rack) + half):
            beam = Box(
                (20.0, 0.0, beam_z),
                (SAMPLE.length, RACK_MEMBER_THICKNESS_M, RACK_MEMBER_THICKNESS_M),
            )
            for name in ("Section1", "Section2", "Load"):
                assert not overlap(found[name], beam), name


def test_load_clears_the_floor_tie_and_nothing_moving_sinks_into_it() -> None:
    found = boxes(carrying=True)
    assert high(found["FloorTie"], 1) == pytest.approx(FLOOR_TIE_HEIGHT_M)
    for name in ("Load", "Section1", "Section2", "Plate", "EndFrameLeft", "EndFrameRight"):
        assert low(found[name], 1) >= FLOOR_TIE_HEIGHT_M - 1e-9, name


def test_a_load_as_long_as_a_cell_fits_between_the_carriage_ends() -> None:
    found = boxes()
    assert low(found["EndFrameRight"], 0) - 20.0 >= SAMPLE.cell_length / 2
    assert 20.0 - high(found["EndFrameLeft"], 0) >= SAMPLE.cell_length / 2
    assert low(found["ColumnRight"], 0) - 20.0 >= SAMPLE.cell_length / 2


def test_forks_at_rest_stay_inside_the_aisle() -> None:
    for name in ("Section1", "Section2"):
        section = boxes()[name]
        assert high(section, 2) <= SAMPLE.aisle_width / 2
        assert low(section, 2) >= -SAMPLE.aisle_width / 2


def test_sections_stand_under_the_two_halves_of_a_cell() -> None:
    found = boxes()
    assert found["Section1"].center[0] == pytest.approx(20.0 - 0.8)
    assert found["Section2"].center[0] == pytest.approx(20.0 + 0.8)
    assert high(found["Section1"], 0) < 20.0 < low(found["Section2"], 0)


def test_there_is_an_opening_between_the_columns_above_the_carriage() -> None:
    # A ray across the aisle at the crane's center, above the carriage and below the top beam.
    for box in boxes().values():
        through_center = low(box, 0) < 20.0 < high(box, 0)
        at_height = low(box, 1) < 8.0 < high(box, 1)
        assert not (through_center and at_height)


REAL_CELLS = create_layout(
    {
        "aisle_count": 1,
        "racks_per_aisle": 2,
        "bays_per_rack": 5,
        "levels_per_rack": 3,
        "cell": {"height_m": 1.5, "length_m": 5.8, "width_m": 2.3},
    }
)


def test_sections_stand_under_the_outer_part_of_a_long_load() -> None:
    assert crane_dimensions(REAL_CELLS).section_x == pytest.approx(2.05)  # 2.9 - 0.85


def test_tines_stay_under_every_part_wherever_the_cut_is() -> None:
    # A load of 5.6 m reaches 2.8 m from the center, and the smallest part is 1.5 m long.
    boxes = crane_boxes(REAL_CELLS, crane_dimensions(REAL_CELLS), 1, (20.0, 0.0))
    assert low(boxes["Section2"], 0) - 20.0 >= 2.8 - 1.5
    assert high(boxes["Section2"], 0) - 20.0 <= 2.8
    assert 20.0 - high(boxes["Section1"], 0) >= 2.8 - 1.5
    assert 20.0 - low(boxes["Section1"], 0) <= 2.8


def test_a_given_load_size_gives_the_box_of_a_carried_load() -> None:
    boxes = crane_boxes(
        REAL_CELLS,
        crane_dimensions(REAL_CELLS),
        1,
        (20.0, 3.0),
        carrying=True,
        load_size=(5.61, 0.33, 2.08),
    )
    assert boxes["Load"].size == (5.61, 0.33, 2.08)
    # It starts at the top of the forks, 0.1125 m above the lift position.
    assert low(boxes["Load"], 1) == pytest.approx(3.1125)
