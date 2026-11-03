"""Finds what a ray selects, from the warehouse layout and state.

This costs the same at any warehouse size, and also finds empty cells, which have no drawn object.
"""

from bisect import insort
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass
from itertools import pairwise
from typing import Protocol

from .layout import Box, Layout, Vector
from .state_source import CellDetails, CraneState, Location, RunState


@dataclass(frozen=True, slots=True)
class Selection:
    kind: str
    aisle: int | None = None
    location: Location | None = None
    key: str | None = None


CraneShape = Callable[[int, CraneState], Iterable[Box]]


class CellSource(Protocol):
    def cell(self, location: Location) -> CellDetails: ...


def _ray_through_box(
    origin: Vector, direction: Vector, low: Vector, high: Vector
) -> tuple[float, float] | None:
    """Returns the entry and exit distances of a ray through a box, or None if it misses."""
    entry = 0.0
    leaving = float("inf")
    for axis in range(3):
        if direction[axis] == 0:
            if origin[axis] < low[axis] or origin[axis] > high[axis]:
                return None
        else:
            first = (low[axis] - origin[axis]) / direction[axis]
            second = (high[axis] - origin[axis]) / direction[axis]
            entry = max(entry, min(first, second))
            leaving = min(leaving, max(first, second))
    return (entry, leaving) if entry < leaving else None


def _ray_hits_box(origin: Vector, direction: Vector, box: Box) -> bool:
    low = tuple(c - s / 2 for c, s in zip(box.center, box.size, strict=True))
    high = tuple(c + s / 2 for c, s in zip(box.center, box.size, strict=True))
    return _ray_through_box(origin, direction, low, high) is not None  # type: ignore[arg-type]


def _crossings(
    origin: Vector,
    direction: Vector,
    axis: int,
    spacing: float,
    count: int,
    limits: list[float],
) -> None:
    """Adds the distances at which a ray crosses from one cell of a rack to the next."""
    if direction[axis] == 0:
        return
    entry, leaving = limits[0], limits[-1]
    for index in range(1, count):
        distance = (index * spacing - origin[axis]) / direction[axis]
        if entry < distance < leaving:
            insort(limits, distance)


def _clamped_index(position: float, spacing: float, count: int) -> int:
    return min(max(int(position // spacing) + 1, 1), count)


def _cells_along_ray(layout: Layout, origin: Vector, direction: Vector) -> Iterator[Location]:
    """Yields the cells along a ray through all racks, nearest first within each rack."""
    half_width = layout.cell_width / 2
    racks = []
    for aisle in range(1, layout.aisle_count + 1):
        for rack in range(1, layout.racks_per_aisle + 1):
            z = layout.rack_z(aisle, rack)
            hit = _ray_through_box(
                origin,
                direction,
                (0.0, 0.0, z - half_width),
                (layout.length, layout.height, z + half_width),
            )
            if hit is not None:
                racks.append((hit[0], hit[1], aisle, rack))
    for entry, leaving, aisle, rack in sorted(racks):
        limits = [entry, leaving]
        _crossings(origin, direction, 0, layout.cell_length, layout.bays, limits)
        _crossings(origin, direction, 1, layout.cell_height, layout.levels, limits)
        for first, second in pairwise(limits):
            middle = (first + second) / 2
            x = origin[0] + direction[0] * middle
            y = origin[1] + direction[1] * middle
            yield (
                aisle,
                rack,
                _clamped_index(x, layout.cell_length, layout.bays),
                _clamped_index(y, layout.cell_height, layout.levels),
            )


def pick_cell(
    layout: Layout,
    origin: Vector,
    direction: Vector,
    is_occupied: Callable[[Location], bool] = lambda _location: False,
) -> Location | None:
    """Returns the first occupied cell along a ray, or otherwise the nearest cell, or None."""
    nearest = None
    for location in _cells_along_ray(layout, origin, direction):
        if nearest is None:
            nearest = location
        if is_occupied(location):
            return location
    return nearest


def pick_crane(
    layout: Layout,
    cranes: Mapping[int, CraneState],
    origin: Vector,
    direction: Vector,
    shape: CraneShape | None = None,
) -> int | None:
    """Returns the aisle of the first crane that a ray hits, or None.

    A shape gives the boxes of a crane as shown, and by default the simple crane's are used.
    """
    for aisle, crane in cranes.items():
        if shape is not None:
            boxes = shape(aisle, crane)
        else:
            boxes = layout.crane_boxes(aisle, crane.position, crane.carrying is not None)
        if any(_ray_hits_box(origin, direction, box) for box in boxes):
            return aisle
    return None


def select_at(
    layout: Layout,
    source: CellSource,
    state: RunState,
    origin: Vector,
    direction: Vector,
    shape: CraneShape | None = None,
) -> Selection | None:
    """Returns what a ray selects: a crane, or otherwise a load unit, or otherwise a cell."""
    aisle = pick_crane(layout, state.cranes, origin, direction, shape)
    if aisle is not None:
        return Selection("crane", aisle=aisle)
    location = pick_cell(
        layout, origin, direction, lambda candidate: source.cell(candidate).load is not None
    )
    if location is None:
        return None
    load = source.cell(location).load
    return Selection("load", key=load.key) if load else Selection("cell", location=location)
