"""3D positions and sizes of warehouse objects. x runs along an aisle, y up, and z across aisles.

Spacing across aisles is for display only, as the simulation does not define it.
"""

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import Any

from .state_source import Location

BLOCK_GAP_SHARE = 0.1
LOAD_SIZE_SHARE = 0.85
CRANE_THICKNESS_SHARE = 0.5
RACK_MEMBER_THICKNESS_M = 0.08

Vector = tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class Box:
    center: Vector
    size: Vector


@dataclass(frozen=True, slots=True)
class Bounds:
    min: Vector
    max: Vector


class Layout:
    def __init__(self, layout: Mapping[str, Any]) -> None:
        self.aisle_count: int = layout["aisle_count"]
        self.racks_per_aisle: int = layout["racks_per_aisle"]
        self.bays: int = layout["bays_per_rack"]
        self.levels: int = layout["levels_per_rack"]
        cell = layout["cell"]
        self.cell_length: float = cell["length_m"]
        self.cell_height: float = cell["height_m"]
        self.cell_width: float = cell["width_m"]
        self.aisle_width: float = self.cell_width
        self.block_width: float = self.racks_per_aisle * self.cell_width + self.aisle_width
        self.block_gap: float = BLOCK_GAP_SHARE * self.cell_width
        self.length = self.bays * self.cell_length
        self.height = self.levels * self.cell_height
        self.cell_count = self.aisle_count * self.racks_per_aisle * self.bays * self.levels
        self._rack_offset: float = (self.aisle_width + self.cell_width) / 2

    def aisle_center_z(self, aisle: int) -> float:
        return (aisle - 1) * (self.block_width + self.block_gap)

    def rack_z(self, aisle: int, rack: int) -> float:
        offset = -self._rack_offset if rack == 1 else self._rack_offset
        return self.aisle_center_z(aisle) + offset

    def end_x(self, end: str) -> float:
        return 0.0 if end == "left" else self.length

    def crane_world_position(self, aisle: int, position: tuple[float, float]) -> Vector:
        return (position[0], position[1], self.aisle_center_z(aisle))

    def cell_box(self, location: Location) -> Box:
        aisle, rack, bay, level = location
        return Box(
            center=(
                (bay - 0.5) * self.cell_length,
                (level - 1) * self.cell_height + self.cell_height / 2,
                self.rack_z(aisle, rack),
            ),
            size=(self.cell_length, self.cell_height, self.cell_width),
        )

    def load_size(self) -> Vector:
        return (
            self.cell_length * LOAD_SIZE_SHARE,
            self.cell_height * LOAD_SIZE_SHARE,
            self.cell_width * LOAD_SIZE_SHARE,
        )

    def pair_base_height(self) -> float:
        """Returns how far above a cell's floor the load in it starts."""
        return (1 - LOAD_SIZE_SHARE) / 2 * self.cell_height

    def mast_size(self) -> Vector:
        return (
            self.cell_length * 0.12,
            self.height,
            self.cell_width * CRANE_THICKNESS_SHARE,
        )

    def platform_size(self) -> Vector:
        return (
            self.cell_length * 0.9,
            self.cell_height * 0.1,
            self.cell_width * CRANE_THICKNESS_SHARE * 1.3,
        )

    def carried_load_height(self) -> float:
        """Returns the height of a carried load's center above the carriage."""
        return self.load_size()[1] / 2 + self.cell_height * 0.05

    def crane_boxes(
        self, aisle: int, position: tuple[float, float], carrying: bool = False
    ) -> list[Box]:
        """Returns the boxes that a crane occupies, for selection."""
        x, y, z = self.crane_world_position(aisle, position)
        boxes = [
            Box((x, self.height / 2, z), self.mast_size()),
            Box((x, y, z), self.platform_size()),
        ]
        if carrying:
            boxes.append(Box((x, y + self.carried_load_height(), z), self.load_size()))
        return boxes

    def bounds(self) -> Bounds:
        return Bounds(
            min=(0.0, 0.0, self.aisle_center_z(1) - self.aisle_width / 2 - self.cell_width),
            max=(
                self.length,
                self.height,
                self.aisle_center_z(self.aisle_count)
                + self.aisle_width / 2
                + (self.cell_width if self.racks_per_aisle == 2 else 0.0),
            ),
        )

    def cell_instance(self, location: Location) -> int:
        """Returns the fixed instance number of a cell, in mixed-radix form."""
        aisle, rack, bay, level = location
        racks = (aisle - 1) * self.racks_per_aisle + (rack - 1)
        return (racks * self.bays + (bay - 1)) * self.levels + (level - 1)

    def cells(self) -> Iterator[Location]:
        """Yields all cells in instance order."""
        for aisle in range(1, self.aisle_count + 1):
            for rack in range(1, self.racks_per_aisle + 1):
                for bay in range(1, self.bays + 1):
                    for level in range(1, self.levels + 1):
                        yield (aisle, rack, bay, level)


def create_layout(layout: Mapping[str, Any]) -> Layout:
    return Layout(layout)
