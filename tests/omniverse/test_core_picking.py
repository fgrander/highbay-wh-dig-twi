"""Finding what a ray selects, with values worked out by hand.

Two aisles, 2 racks each, 5 bays and 2 levels, with cells 4 m long, 3 m high, and 1.5 m wide.
Aisle 1 is at z = 0: rack 1 spans z -2.25 to -0.75, and rack 2 spans z 0.75 to 2.25.
Aisle 2 is at z = 4.65: rack 1 spans z 2.4 to 3.9, and rack 2 spans z 5.4 to 6.9.
"""

import pytest

from highbay.replay.core.layout import create_layout
from highbay.replay.core.picking import Selection, pick_cell, pick_crane, select_at
from highbay.replay.core.state_source import (
    Backlog,
    CellDetails,
    CraneState,
    LoadUnit,
    Location,
    RunState,
)

LAYOUT = create_layout(
    {
        "aisle_count": 2,
        "racks_per_aisle": 2,
        "bays_per_rack": 5,
        "levels_per_rack": 2,
        "cell": {"height_m": 3.0, "length_m": 4.0, "width_m": 1.5},
    }
)


@pytest.mark.parametrize(
    ("origin", "direction", "expected"),
    [
        # From outside, across the aisles.
        ((10.0, 4.5, 100.0), (0.0, 0.0, -1.0), (2, 2, 3, 2)),
        ((10.0, 4.5, -100.0), (0.0, 0.0, 1.0), (1, 1, 3, 2)),
        # From inside aisle 1, toward each of its racks.
        ((2.0, 1.0, 0.0), (0.0, 0.0, 1.0), (1, 2, 1, 1)),
        ((18.0, 1.0, 0.0), (0.0, 0.0, -1.0), (1, 1, 5, 1)),
        # From above, straight down onto the top level.
        ((6.0, 50.0, 1.5), (0.0, -1.0, 0.0), (1, 2, 2, 2)),
    ],
)
def test_nearest_cell_with_nothing_occupied(
    origin: tuple[float, float, float],
    direction: tuple[float, float, float],
    expected: Location,
) -> None:
    assert pick_cell(LAYOUT, origin, direction) == expected


def test_ray_that_misses_all_racks_finds_nothing() -> None:
    assert pick_cell(LAYOUT, (10.0, 100.0, 0.0), (0.0, 1.0, 0.0)) is None
    assert pick_cell(LAYOUT, (2.0, 1.0, 0.0), (1.0, 0.0, 0.0)) is None


def test_first_occupied_cell_is_seen_through_empty_cells() -> None:
    occupied: set[Location] = {(1, 2, 3, 2)}
    found = pick_cell(LAYOUT, (10.0, 4.5, 100.0), (0.0, 0.0, -1.0), occupied.__contains__)
    assert found == (1, 2, 3, 2)


def test_occupied_cell_in_the_same_rack_along_the_ray() -> None:
    # Along rack 1 of aisle 1 at level 1, from bay 1 toward bay 5.
    occupied: set[Location] = {(1, 1, 4, 1)}
    found = pick_cell(LAYOUT, (-10.0, 1.0, -1.5), (1.0, 0.0, 0.0), occupied.__contains__)
    assert found == (1, 1, 4, 1)


def crane(aisle: int, position: tuple[float, float], carrying: str | None = None) -> CraneState:
    return CraneState(aisle, "idle", None, carrying, position, None)


def test_crane_is_found_by_its_mast_and_its_carriage() -> None:
    cranes = {1: crane(1, (8.0, 3.0)), 2: crane(2, (12.0, 0.0))}
    # The mast of crane 2 stands at x = 12 and z = 4.65, from y = 0 to 6.
    assert pick_crane(LAYOUT, cranes, (12.0, 3.0, 100.0), (0.0, 0.0, -1.0)) == 2
    # The carriage of crane 1 is 3.6 m long at y = 3, and the mast is only 0.48 m long.
    assert pick_crane(LAYOUT, cranes, (9.5, 3.0, -100.0), (0.0, 0.0, 1.0)) == 1
    assert pick_crane(LAYOUT, cranes, (9.5, 5.0, -100.0), (0.0, 0.0, 1.0)) is None


def test_carried_load_counts_as_the_crane_only_when_there() -> None:
    # A load unit is 3.4 m long, 2.55 m high, and sits above the carriage at y = 3.
    origin = (9.5, 4.5, -100.0)
    direction = (0.0, 0.0, 1.0)
    assert pick_crane(LAYOUT, {1: crane(1, (8.0, 3.0))}, origin, direction) is None
    assert pick_crane(LAYOUT, {1: crane(1, (8.0, 3.0), "o1")}, origin, direction) == 1


class Source:
    """The part of a state source that selection needs."""

    def __init__(self, loads: dict[Location, str]) -> None:
        self.loads = loads

    def cell(self, location: Location) -> CellDetails:
        key = self.loads.get(location)
        if key is None:
            return CellDetails(location, "free", None)
        return CellDetails(location, "occupied", LoadUnit(key, 0, None, None, location, None))


def state(cranes: dict[int, CraneState]) -> RunState:
    return RunState(0.0, False, Backlog(0, {}, 0), 0, 0.0, 0, 0, 0, cranes)


def test_selection_prefers_cranes_then_load_units_then_cells() -> None:
    source = Source({(1, 2, 3, 2): "i0"})
    cranes = {1: crane(1, (10.0, 0.0))}
    origin = (10.0, 4.5, 100.0)
    down = (0.0, 0.0, -1.0)
    # Through the mast of crane 1 at x = 10, which is in front of rack 1 of aisle 1.
    assert select_at(LAYOUT, source, state(cranes), origin, down) == Selection("crane", aisle=1)
    # Past the crane, the load unit in rack 2 of aisle 1 at bay 3 and level 2.
    elsewhere = state({1: crane(1, (18.0, 0.0))})
    assert select_at(LAYOUT, source, elsewhere, origin, down) == Selection("load", key="i0")
    # With nothing stored along the ray, the nearest cell.
    empty = Source({})
    nearest = Selection("cell", location=(2, 2, 3, 2))
    assert select_at(LAYOUT, empty, elsewhere, origin, down) == nearest
    # Anywhere else, nothing.
    assert select_at(LAYOUT, empty, elsewhere, (10.0, 100.0, 0.0), (0.0, 1.0, 0.0)) is None
