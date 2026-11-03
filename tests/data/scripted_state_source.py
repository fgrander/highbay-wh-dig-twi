"""A state source written only from contracts/state-interface.md, as a later live source could be.

It has no recording. Its time range grows while it runs, it cannot move backward, and it has no
reported values. One crane moves at a constant speed along its aisle, and one load unit stays in a
cell until the crane has passed the middle of the aisle.
"""

from highbay.replay.core.state_source import (
    Backlog,
    CellChanges,
    CellDetails,
    CraneState,
    LoadUnit,
    Location,
    OrderDetails,
    RunState,
    WarehouseDescription,
)

CELL: Location = (1, 1, 2, 1)
LOAD_KEY = "scripted"
CRANE_SPEED_M_S = 0.1
LEAVES_CELL_AT_S = 40.0
ARTICLES = ["scripted article"]


class ScriptedSource:
    range_is_final = False
    can_move_backward = False

    def __init__(self, end_s: float = 10.0) -> None:
        self._end_s = end_s
        self._time_s = 0.0
        self._cell_changed = True

    def grow(self, end_s: float) -> None:
        self._end_s = end_s

    def describe(self) -> WarehouseDescription:
        return WarehouseDescription(
            layout={
                "aisle_count": 1,
                "racks_per_aisle": 2,
                "bays_per_rack": 4,
                "levels_per_rack": 2,
                "cell": {"height_m": 2.0, "length_m": 3.0, "width_m": 1.0},
            },
            crane={
                "horizontal": {"speed_m_s": 1.0, "acceleration_m_s2": 1.0},
                "vertical": {"speed_m_s": 1.0, "acceleration_m_s2": 1.0},
                "pick_time_s": 1.0,
                "set_time_s": 1.0,
            },
            transfer_points={"1": {"left": ["inbound"], "right": ["outbound"]}},
            crane_start_positions={"1": [0.0, 0.0]},
            articles=ARTICLES,
        )

    def time_range(self) -> tuple[float, float]:
        return (0.0, self._end_s)

    def _stored(self) -> bool:
        return self._time_s < LEAVES_CELL_AT_S

    def state_at(self, time_s: float) -> RunState:
        if time_s < self._time_s or time_s > self._end_s:
            raise ValueError(f"{time_s} is not available")
        stored_before = self._stored()
        self._time_s = time_s
        self._cell_changed = self._cell_changed or stored_before != self._stored()
        stored = self._stored()
        return RunState(
            time_s=time_s,
            in_measurement_window=True,
            backlog=Backlog(0, {1: 0}, 0),
            occupied_cells=1 if stored else 0,
            occupancy=(1 if stored else 0) / 16,
            completed=0,
            arrived=0,
            unfulfillable=0,
            cranes={
                1: CraneState(
                    aisle=1,
                    activity="moving_empty",
                    order=None,
                    carrying=None,
                    position=(time_s * CRANE_SPEED_M_S, 0.0),
                    movement_target=None,
                )
            },
        )

    def take_changes(self) -> CellChanges:
        changes = CellChanges(False, [CELL] if self._cell_changed else [])
        self._cell_changed = False
        return changes

    def stored_load_units(self) -> list[LoadUnit]:
        loaded = self.load(LOAD_KEY)
        return [loaded] if loaded is not None else []

    def cell(self, location: Location) -> CellDetails:
        if location == CELL and self._stored():
            return CellDetails(location, "occupied", self.load(LOAD_KEY))
        return CellDetails(location, "free", None)

    def load(self, key: str) -> LoadUnit | None:
        if key != LOAD_KEY or not self._stored():
            return None
        return LoadUnit(LOAD_KEY, 0, None, None, CELL, None)

    def order(self, index: int) -> OrderDetails:
        raise ValueError(f"This source has no order {index}")
