"""The plant model, driven directly through its signals.

The warehouse has cells 4 m long and 3 m high, one rack, 5 bays, and 2 levels. Horizontal: 2 m/s and
1 m/s². Vertical: 1 m/s and 1 m/s². Pick and set take 10 s. Inbound is left, outbound is right.
A move to bay 3, level 2 is 10 m and 3 m: horizontal 10/2 + 2/1 = 7 s, vertical 3/1 + 1/1 = 4 s.
"""

import pytest

from conftest import minimal_warehouse_dict
from highbay_sim.config import WarehouseDefinition
from highbay_sim.kinematics import axis_position
from highbay_sim.plant import Plant
from highbay_sim.signals import CraneSignals

CELL = (1, 1, 3, 2)
CELL_POSITION = (10.0, 3.0)
RIGHT_END = (20.0, 0.0)


class Observer:
    def __init__(self) -> None:
        self.seen: list[tuple[object, ...]] = []

    def movement_started(
        self,
        aisle: int,
        time_s: float,
        start: tuple[float, float],
        target: tuple[float, float],
        end_s: float,
        loaded: bool,
    ) -> None:
        self.seen.append(("move", aisle, time_s, start, target, end_s, loaded))

    def handling_started(self, aisle: int, time_s: float, end_s: float) -> None:
        self.seen.append(("handling", aisle, time_s, end_s))

    def pick_finished(self, aisle: int, time_s: float, place: object) -> None:
        self.seen.append(("picked", aisle, time_s))

    def set_finished(self, aisle: int, time_s: float, place: object) -> None:
        self.seen.append(("set", aisle, time_s))


class Rig:
    def __init__(
        self, cycle_ms: int = 100, stock: dict[tuple[int, int, int, int], str] | None = None
    ) -> None:
        content = minimal_warehouse_dict()
        content["initial_stock"] = [
            {
                "location": dict(zip(("aisle", "rack", "bay", "level"), location, strict=True)),
                "article": article,
            }
            for location, article in (stock or {}).items()
        ]
        self.warehouse = WarehouseDefinition.model_validate(content)
        self.observer = Observer()
        self.signals = {1: CraneSignals()}
        self.crane = self.signals[1]
        self.plant = Plant(self.warehouse, cycle_ms, self.signals, self.observer)
        self.cycle = 0

    def run(self, cycles: int) -> None:
        """Advance with rising-edge commands cleared after the first cycle."""
        for _ in range(cycles):
            self.plant.advance(self.cycle)
            self.cycle += 1
            self.crane.horizontal_start = self.crane.vertical_start = False
            self.crane.pick_start = self.crane.set_start = False

    def move(self, horizontal_m: float, vertical_m: float) -> None:
        self.crane.horizontal_target_m = horizontal_m
        self.crane.vertical_target_m = vertical_m
        self.crane.horizontal_start = self.crane.vertical_start = True

    def actual(self) -> tuple[float, float]:
        return self.crane.horizontal_actual_m, self.crane.vertical_actual_m


def test_crane_starts_at_the_first_inbound_end_at_rest() -> None:
    crane = Rig().crane
    assert (crane.horizontal_actual_m, crane.vertical_actual_m) == (0.0, 0.0)
    assert crane.horizontal_in_position and crane.vertical_in_position
    assert not crane.load_present
    assert not crane.handling_active
    assert crane.fault_code == 0


def test_position_follows_the_profile_at_each_boundary() -> None:
    rig = Rig()
    rig.move(*CELL_POSITION)
    for cycle in range(1, 71):
        rig.run(1)
        elapsed = cycle * 0.1
        assert rig.crane.horizontal_actual_m == pytest.approx(
            axis_position(0.0, 10.0, 2.0, 1.0, elapsed)
        )
        assert rig.crane.vertical_actual_m == pytest.approx(
            axis_position(0.0, 3.0, 1.0, 1.0, elapsed)
        )


def test_hand_calculated_positions_after_one_second() -> None:
    rig = Rig()
    rig.move(*CELL_POSITION)
    rig.run(10)
    # Each axis has covered a·t²/2 = 0.5 m.
    assert rig.actual() == pytest.approx((0.5, 0.5))


def test_each_axis_reports_in_position_at_its_own_end() -> None:
    rig = Rig()
    rig.move(*CELL_POSITION)
    rig.run(39)
    assert not rig.crane.vertical_in_position
    rig.run(1)  # 4 s
    assert rig.crane.vertical_in_position
    assert rig.crane.vertical_actual_m == 3.0
    assert not rig.crane.horizontal_in_position
    rig.run(29)
    assert not rig.crane.horizontal_in_position
    rig.run(1)  # 7 s
    assert rig.crane.horizontal_in_position
    assert rig.crane.horizontal_actual_m == 10.0


def test_an_axis_ends_on_the_first_boundary_at_or_after_its_exact_end() -> None:
    # At 300 ms, 7 s is 23.33 cycles, so the horizontal axis arrives at cycle 24.
    rig = Rig(cycle_ms=300)
    rig.move(*CELL_POSITION)
    rig.run(23)
    assert not rig.crane.horizontal_in_position
    rig.run(1)
    assert rig.crane.horizontal_in_position
    assert rig.crane.horizontal_actual_m == 10.0


def test_a_long_cycle_never_overshoots_the_target() -> None:
    rig = Rig(cycle_ms=1000)
    rig.move(2.0, 0.0)
    for _ in range(5):
        rig.run(1)
        assert 0.0 <= rig.crane.horizontal_actual_m <= 2.0
    assert rig.crane.horizontal_actual_m == 2.0


def test_holding_a_start_true_does_not_start_again() -> None:
    rig = Rig()
    rig.move(2.0, 0.0)
    rig.plant.advance(0)
    rig.crane.horizontal_target_m = 6.0
    # horizontal_start is still true: no rising edge, so the new target is not used.
    for cycle in range(1, 60):
        rig.plant.advance(cycle)
    assert rig.crane.horizontal_actual_m == 2.0


def test_a_new_edge_starts_a_new_movement_from_where_the_crane_is() -> None:
    rig = Rig()
    rig.move(2.0, 0.0)
    rig.run(30)
    rig.move(0.0, 0.0)
    rig.run(1)
    assert rig.crane.horizontal_actual_m == pytest.approx(2.0 - 0.005)  # a·t²/2 at 0.1 s


def test_movement_is_reported_when_it_starts_with_its_rounded_end() -> None:
    rig = Rig(cycle_ms=300)
    rig.move(*CELL_POSITION)
    rig.run(1)
    assert rig.observer.seen == [
        ("move", 1, 0.0, (0.0, 0.0), CELL_POSITION, pytest.approx(7.2), False)
    ]


def test_movement_of_zero_distance_reports_nothing_and_stays_in_position() -> None:
    rig = Rig()
    rig.move(0.0, 0.0)
    rig.run(1)
    assert rig.observer.seen == []
    assert rig.crane.horizontal_in_position


def test_one_axis_keeps_the_other_at_its_position() -> None:
    rig = Rig()
    rig.crane.vertical_target_m = 3.0
    rig.crane.vertical_start = True
    rig.run(1)
    assert rig.observer.seen[0][4] == (0.0, 3.0)


def go_to(rig: Rig, horizontal_m: float, vertical_m: float) -> None:
    rig.move(horizontal_m, vertical_m)
    rig.run(130)


def test_pick_takes_its_time_and_moves_the_load_when_it_ends() -> None:
    rig = Rig(stock={CELL: "A"})
    go_to(rig, *CELL_POSITION)
    rig.observer.seen.clear()
    rig.crane.side = 1
    rig.crane.pick_start = True
    rig.run(99)
    assert rig.crane.handling_active
    assert not rig.crane.load_present
    assert rig.plant.cell_contents() == {CELL: "A"}
    rig.run(1)
    assert not rig.crane.handling_active
    assert rig.crane.load_present
    assert rig.plant.cell_contents() == {}
    assert rig.plant.load_on_crane(1) == "A"
    assert rig.observer.seen == [
        ("handling", 1, 13.0, pytest.approx(23.0)),
        ("picked", 1, pytest.approx(23.0)),
    ]


def test_set_stores_the_load_when_it_ends() -> None:
    rig = Rig(stock={CELL: "A"})
    go_to(rig, *CELL_POSITION)
    rig.crane.side = 1
    rig.crane.pick_start = True
    rig.run(100)
    go_to(rig, 2.0, 0.0)
    rig.crane.set_start = True
    rig.run(99)
    assert rig.crane.load_present
    rig.run(1)
    assert not rig.crane.load_present
    assert rig.plant.cell_contents() == {(1, 1, 1, 1): "A"}


def test_load_set_at_an_outbound_end_leaves_the_warehouse() -> None:
    rig = Rig(stock={CELL: "A"})
    go_to(rig, *CELL_POSITION)
    rig.crane.side = 1
    rig.crane.pick_start = True
    rig.run(100)
    go_to(rig, *RIGHT_END)
    rig.crane.set_start = True
    rig.run(100)
    assert not rig.crane.load_present
    assert rig.plant.cell_contents() == {}
    assert rig.plant.load_on_crane(1) is None


def test_offered_load_is_picked_at_an_inbound_end() -> None:
    rig = Rig()
    rig.plant.offer_load(1, "left", "A")
    rig.crane.pick_start = True
    rig.run(100)
    assert rig.plant.load_on_crane(1) == "A"
    assert rig.crane.load_present


def test_position_within_a_millimeter_counts_as_the_place() -> None:
    rig = Rig(stock={CELL: "A"})
    go_to(rig, CELL_POSITION[0] + 0.0009, CELL_POSITION[1] - 0.0009)
    rig.crane.side = 1
    rig.crane.pick_start = True
    rig.run(100)
    assert rig.plant.load_on_crane(1) == "A"


def test_handling_rounds_up_to_a_boundary() -> None:
    # At 300 ms, 10 s is 33.33 cycles, so a pick takes 34 cycles.
    rig = Rig(cycle_ms=300)
    rig.plant.offer_load(1, "left", "A")
    rig.crane.pick_start = True
    rig.run(33)
    assert rig.crane.handling_active
    rig.run(1)
    assert not rig.crane.handling_active


def test_writing_to_status_signals_changes_nothing_in_the_plant() -> None:
    rig = Rig()
    rig.move(*CELL_POSITION)
    rig.run(10)
    rig.crane.horizontal_actual_m = 99.0
    rig.crane.horizontal_in_position = True
    rig.crane.load_present = True
    rig.run(1)
    assert rig.crane.horizontal_actual_m == pytest.approx(axis_position(0.0, 10.0, 2.0, 1.0, 1.1))
    assert not rig.crane.horizontal_in_position
    assert not rig.crane.load_present
    assert rig.plant.load_on_crane(1) is None


def test_writing_to_status_signals_at_rest_changes_nothing_either() -> None:
    rig = Rig()
    rig.crane.horizontal_actual_m = 7.0
    rig.crane.vertical_actual_m = 7.0
    rig.crane.horizontal_in_position = False
    rig.crane.fault_code = 3
    rig.run(1)
    assert rig.actual() == (0.0, 0.0)
    assert rig.crane.horizontal_in_position
    assert rig.crane.fault_code == 0


def test_each_load_unit_is_in_exactly_one_place_throughout() -> None:
    rig = Rig(stock={CELL: "A"})
    go_to(rig, *CELL_POSITION)
    rig.crane.side = 1
    rig.crane.pick_start = True
    for _ in range(100):
        rig.run(1)
        in_cells = len(rig.plant.cell_contents())
        on_crane = 0 if rig.plant.load_on_crane(1) is None else 1
        assert in_cells + on_crane == 1
