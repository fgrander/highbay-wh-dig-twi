"""Positions and sizes for the Omniverse replay, with values worked out by hand."""

import pytest

from highbay.replay.core.layout import create_layout

LAYOUT = {
    "aisle_count": 2,
    "racks_per_aisle": 2,
    "bays_per_rack": 5,
    "levels_per_rack": 3,
    "cell": {"height_m": 2.0, "length_m": 4.0, "width_m": 1.0},
}


def test_dimensions() -> None:
    layout = create_layout(LAYOUT)
    assert layout.length == 20.0
    assert layout.height == 6.0
    assert layout.aisle_width == 1.0
    assert layout.block_width == 3.0  # 2 racks of 1 m and an aisle of 1 m
    assert layout.block_gap == pytest.approx(0.1)
    assert layout.cell_count == 60  # 2 * 2 * 5 * 3


def test_aisles_and_racks_across_the_warehouse() -> None:
    layout = create_layout(LAYOUT)
    assert layout.aisle_center_z(1) == 0.0
    assert layout.aisle_center_z(2) == pytest.approx(3.1)
    assert layout.rack_z(1, 1) == -1.0  # (1 + 1) / 2 from the aisle's center
    assert layout.rack_z(1, 2) == 1.0
    assert layout.rack_z(2, 2) == pytest.approx(4.1)


def test_cell_box() -> None:
    box = create_layout(LAYOUT).cell_box((2, 1, 3, 2))
    assert box.center == pytest.approx((10.0, 3.0, 2.1))  # 2.5 * 4, 1 * 2 + 1, 3.1 - 1
    assert box.size == (4.0, 2.0, 1.0)


def test_crane_world_position_and_aisle_ends() -> None:
    layout = create_layout(LAYOUT)
    assert layout.crane_world_position(2, (7.0, 3.0)) == pytest.approx((7.0, 3.0, 3.1))
    assert layout.end_x("left") == 0.0
    assert layout.end_x("right") == 20.0


def test_bounds_with_two_racks() -> None:
    bounds = create_layout(LAYOUT).bounds()
    assert bounds.min == pytest.approx((0.0, 0.0, -1.5))  # -0.5 - 1
    assert bounds.max == pytest.approx((20.0, 6.0, 4.6))  # 3.1 + 0.5 + 1


def test_bounds_with_one_rack() -> None:
    bounds = create_layout({**LAYOUT, "racks_per_aisle": 1}).bounds()
    # A block is 2 m wide with one rack, so the second aisle is at 2.1 m, and nothing is beyond it.
    assert bounds.max[2] == pytest.approx(2.6)


def test_instance_number_is_mixed_radix_and_covers_all_cells() -> None:
    layout = create_layout(LAYOUT)
    assert layout.cell_instance((1, 1, 1, 1)) == 0
    assert layout.cell_instance((1, 1, 1, 2)) == 1
    assert layout.cell_instance((1, 1, 2, 1)) == 3
    assert layout.cell_instance((1, 2, 1, 1)) == 15
    assert layout.cell_instance((2, 1, 1, 1)) == 30
    assert layout.cell_instance((2, 2, 5, 3)) == 59


def test_cells_in_instance_order() -> None:
    layout = create_layout(LAYOUT)
    cells = list(layout.cells())
    assert len(cells) == 60
    assert [layout.cell_instance(cell) for cell in cells] == list(range(60))


def test_load_in_a_cell_starts_above_the_cells_floor() -> None:
    layout = create_layout(LAYOUT)
    assert layout.load_base_height() == pytest.approx(0.15)  # (1 - 0.85) / 2 of 2 m
    box = layout.cell_box((1, 1, 1, 1))
    assert box.center[1] - layout.load_size()[1] / 2 == pytest.approx(layout.load_base_height())
