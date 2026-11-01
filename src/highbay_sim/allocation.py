"""Free cells, stock, and storage location rules."""

import heapq
from collections import deque
from typing import Final, Literal

from highbay_sim.config import End, Layout, WarehouseDefinition
from highbay_sim.events import Location
from highbay_sim.kinematics import movement_time
from highbay_sim.orders import stream_rng

CellState = Literal["free", "reserved_for_storage", "occupied", "reserved_for_retrieval"]
FREE: Final = "free"
RESERVED_FOR_STORAGE: Final = "reserved_for_storage"
OCCUPIED: Final = "occupied"
RESERVED_FOR_RETRIEVAL: Final = "reserved_for_retrieval"


def cell_position(layout: Layout, location: Location) -> tuple[float, float]:
    """Return a cell's (horizontal, vertical) position: its bay's center and its level's floor."""
    _, _, bay, level = location
    return (bay - 0.5) * layout.cell.length_m, (level - 1) * layout.cell.height_m


def end_position(layout: Layout, end: End) -> tuple[float, float]:
    """Return the position of an aisle end, which is at ground level."""
    return (0.0 if end == "left" else layout.bays_per_rack * layout.cell.length_m), 0.0


class Allocation:
    """Tracks every cell's state and the available stock of each article."""

    def __init__(self, warehouse: WarehouseDefinition, seed: int) -> None:
        self._warehouse = warehouse
        self._layout = warehouse.layout
        self._uses_nearest_rule = warehouse.storage_rule == "nearest_free"
        self._rng = stream_rng(seed, "storage")
        self._nearest_times: dict[tuple[tuple[End, ...], int, int], float] = {}
        self._inbound_ends = {
            aisle: tuple(warehouse.ends_with_role(aisle, "inbound"))
            for aisle in range(1, self._layout.aisle_count + 1)
        }
        self._stock: dict[str, deque[Location]] = {}
        self._states: dict[Location, CellState] = {
            location: FREE for location in self._all_locations()
        }

        for location, article in sorted(
            (
                (
                    (
                        entry.location.aisle,
                        entry.location.rack,
                        entry.location.bay,
                        entry.location.level,
                    ),
                    entry.article,
                )
                for entry in warehouse.initial_stock
            ),
        ):
            self._store_initial(location, article)
        self.initial_occupied = len(warehouse.initial_stock)

        free = [location for location, state in self._states.items() if state == FREE]
        self._free_list = free
        self._free_heap = (
            [(self._nearest_time(location), location) for location in free]
            if (self._uses_nearest_rule)
            else []
        )
        heapq.heapify(self._free_heap)

    @property
    def cell_count(self) -> int:
        return len(self._states)

    def state(self, location: Location) -> CellState:
        return self._states[location]

    def _store_initial(self, location: Location, article: str) -> None:
        self._states[location] = OCCUPIED
        self._stock.setdefault(article, deque()).append(location)

    def reserve_for_storage(self) -> Location | None:
        """Reserve a free cell under the storage rule, or return None if no cell is free."""
        location = self._take_free_cell()
        if location is not None:
            self._states[location] = RESERVED_FOR_STORAGE
        return location

    def store(self, location: Location, article: str) -> None:
        """Record a load unit set down in its reserved cell, making it available as stock."""
        self._require_state(location, RESERVED_FOR_STORAGE)
        self._states[location] = OCCUPIED
        self._stock.setdefault(article, deque()).append(location)

    def reserve_for_retrieval(self, article: str) -> Location | None:
        """Reserve the oldest stored load unit of an article, or return None if there is none."""
        stock = self._stock.get(article)
        if not stock:
            return None
        location = stock.popleft()
        self._states[location] = RESERVED_FOR_RETRIEVAL
        return location

    def release(self, location: Location) -> None:
        """Free a cell whose load unit has been picked up."""
        self._require_state(location, RESERVED_FOR_RETRIEVAL)
        self._states[location] = FREE
        if self._uses_nearest_rule:
            heapq.heappush(self._free_heap, (self._nearest_time(location), location))
        else:
            self._free_list.append(location)

    def _all_locations(self) -> list[Location]:
        return [
            (aisle, rack, bay, level)
            for aisle in range(1, self._layout.aisle_count + 1)
            for rack in range(1, self._layout.racks_per_aisle + 1)
            for bay in range(1, self._layout.bays_per_rack + 1)
            for level in range(1, self._layout.levels_per_rack + 1)
        ]

    def _take_free_cell(self) -> Location | None:
        if self._uses_nearest_rule:
            return heapq.heappop(self._free_heap)[1] if self._free_heap else None
        if not self._free_list:
            return None
        index = self._rng.randrange(len(self._free_list))
        self._free_list[index], self._free_list[-1] = self._free_list[-1], self._free_list[index]
        return self._free_list.pop()

    def _nearest_time(self, location: Location) -> float:
        """Return the shortest travel time to a cell from an inbound point of its aisle."""
        aisle, _, bay, level = location
        ends = self._inbound_ends[aisle]
        key = (ends, bay, level)
        cached = self._nearest_times.get(key)
        if cached is not None:
            return cached
        crane = self._warehouse.crane
        cell_x, cell_z = cell_position(self._layout, location)
        time_s = min(
            movement_time(
                cell_x - end_position(self._layout, end)[0],
                cell_z,
                crane.horizontal.speed_m_s,
                crane.horizontal.acceleration_m_s2,
                crane.vertical.speed_m_s,
                crane.vertical.acceleration_m_s2,
            )
            for end in ends
        )
        self._nearest_times[key] = time_s
        return time_s

    def _require_state(self, location: Location, expected: CellState) -> None:
        if self._states[location] != expected:
            raise ValueError(f"cell {location} is {self._states[location]}, expected {expected}")
