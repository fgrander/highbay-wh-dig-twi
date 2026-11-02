"""Finding a cell from a ray, with values worked out by hand.

Two aisles, 2 racks each, 5 bays and 2 levels, with cells 4 m long, 3 m high, and 1.5 m wide.
Aisle 1 is at z = 0: rack 1 spans z -2.25 to -0.75, and rack 2 spans z 0.75 to 2.25.
Aisle 2 is at z = 4.65: rack 1 spans z 2.4 to 3.9, and rack 2 spans z 5.4 to 6.9.
"""

from typing import Any

import pytest

from conftest import Modules

LAYOUT = {
    "aisle_count": 2,
    "racks_per_aisle": 2,
    "bays_per_rack": 5,
    "levels_per_rack": 2,
    "cell": {"height_m": 3.0, "length_m": 4.0, "width_m": 1.5},
}


def pick(
    modules: Modules,
    origin: list[float],
    direction: list[float],
    occupied: list[list[int]] | None = None,
) -> Any:
    return modules.run(
        "const { createLayout } = await imports('layout.js');"
        "const { pickCell } = await imports('picking.js');"
        "const occupied = new Set(args[3].map((location) => location.join('-')));"
        "return pickCell(createLayout(args[0]), { origin: args[1], direction: args[2] },"
        " (location) => occupied.has(location.join('-')));",
        LAYOUT,
        origin,
        direction,
        occupied or [],
    )


@pytest.mark.parametrize(
    ("origin", "direction", "expected"),
    [
        # From outside, across the aisles.
        ([10.0, 4.5, 100.0], [0.0, 0.0, -1.0], [2, 2, 3, 2]),
        ([10.0, 4.5, -100.0], [0.0, 0.0, 1.0], [1, 1, 3, 2]),
        # From inside aisle 1, toward each of its racks.
        ([2.0, 1.0, 0.0], [0.0, 0.0, 1.0], [1, 2, 1, 1]),
        ([18.0, 1.0, 0.0], [0.0, 0.0, -1.0], [1, 1, 5, 1]),
        # Along a rack, entering at its end.
        ([-10.0, 1.0, -1.5], [1.0, 0.0, 0.0], [1, 1, 1, 1]),
        ([30.0, 4.0, 6.0], [-1.0, 0.0, 0.0], [2, 2, 5, 2]),
        # From above, entering the top level.
        ([2.0, 100.0, -1.5], [0.0, -1.0, 0.0], [1, 1, 1, 2]),
        # Through the gap between aisle blocks, continuing to the next rack.
        ([6.0, 1.0, 2.3], [0.0, 0.0, 1.0], [2, 1, 2, 1]),
    ],
)
def test_nearest_cell_when_no_cell_is_occupied(
    modules: Modules, origin: list[float], direction: list[float], expected: list[int]
) -> None:
    assert pick(modules, origin, direction) == expected


@pytest.mark.parametrize(
    ("origin", "direction"),
    [
        ([10.0, 100.0, 0.0], [0.0, -1.0, 0.0]),  # straight down an aisle
        ([-10.0, 1.0, 0.0], [1.0, 0.0, 0.0]),  # along an aisle
        ([10.0, 4.5, 100.0], [0.0, 0.0, 1.0]),  # pointing away
        ([10.0, 50.0, 100.0], [0.0, 0.0, -1.0]),  # passing above
    ],
)
def test_ray_that_hits_no_rack_gives_nothing(
    modules: Modules, origin: list[float], direction: list[float]
) -> None:
    assert pick(modules, origin, direction) is None


def test_occupied_cell_is_found_through_empty_cells_in_the_same_rack(modules: Modules) -> None:
    ray = ([-10.0, 1.0, -1.5], [1.0, 0.0, 0.0])
    assert pick(modules, *ray, occupied=[[1, 1, 4, 1]]) == [1, 1, 4, 1]


def test_occupied_cell_is_found_through_empty_racks(modules: Modules) -> None:
    ray = ([10.0, 4.5, 100.0], [0.0, 0.0, -1.0])
    assert pick(modules, *ray, occupied=[[1, 1, 3, 2]]) == [1, 1, 3, 2]


def test_nearest_of_several_occupied_cells_is_chosen(modules: Modules) -> None:
    ray = ([10.0, 4.5, 100.0], [0.0, 0.0, -1.0])
    occupied = [[1, 1, 3, 2], [2, 1, 3, 2]]
    assert pick(modules, *ray, occupied=occupied) == [2, 1, 3, 2]


def test_occupied_cell_off_the_ray_changes_nothing(modules: Modules) -> None:
    ray = ([10.0, 4.5, 100.0], [0.0, 0.0, -1.0])
    assert pick(modules, *ray, occupied=[[1, 1, 3, 1]]) == [2, 2, 3, 2]


def test_diagonal_ray_crosses_cells_in_order(modules: Modules) -> None:
    # Down through rack 1 of aisle 1 at z = -1.5: enters at the top of bay 1, and leaves by bay 2.
    ray = ([1.0, 6.5, -1.5], [1.0, -1.0, 0.0])
    assert pick(modules, *ray) == [1, 1, 1, 2]
    assert pick(modules, *ray, occupied=[[1, 1, 2, 1]]) == [1, 1, 2, 1]
