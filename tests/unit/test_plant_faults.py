"""Commands that the plant cannot carry out, one case for each code in the signal list."""

import pytest
from test_plant import CELL, CELL_POSITION, RIGHT_END, Observer, Rig, go_to

from conftest import minimal_warehouse_dict
from highbay_sim.config import WarehouseDefinition
from highbay_sim.plant import Plant
from highbay_sim.signals import CraneSignals, FaultCode


def loads(rig: Rig) -> int:
    return len(rig.plant.cell_contents()) + (0 if rig.plant.load_on_crane(1) is None else 1)


def assert_fault(rig: Rig, code: FaultCode) -> None:
    assert rig.crane.fault_code == code
    fault = rig.plant.faults[-1]
    assert fault.code == code
    assert fault.crane == 1
    assert fault.description


def picked(rig: Rig) -> None:
    """Leave the crane at its cell position with the load of the cell on it."""
    go_to(rig, *CELL_POSITION)
    rig.crane.side = 1
    rig.crane.pick_start = True
    rig.run(100)
    assert rig.plant.load_on_crane(1) is not None


@pytest.mark.parametrize(
    ("horizontal_m", "vertical_m"), [(20.5, 0.0), (-0.5, 0.0), (0.0, 3.5), (0.0, -0.5)]
)
def test_target_out_of_range(horizontal_m: float, vertical_m: float) -> None:
    rig = Rig()
    rig.move(horizontal_m, vertical_m)
    rig.run(10)
    assert_fault(rig, FaultCode.TARGET_OUT_OF_RANGE)
    assert rig.actual() == (0.0, 0.0)


def test_target_at_the_ends_of_travel_is_allowed() -> None:
    rig = Rig()
    rig.move(20.0, 3.0)
    rig.run(1)
    assert rig.crane.fault_code == 0


def test_a_start_while_moving_is_refused_and_the_movement_finishes() -> None:
    rig = Rig()
    rig.move(*CELL_POSITION)
    rig.run(10)
    rig.move(0.0, 0.0)
    rig.run(1)
    assert_fault(rig, FaultCode.CRANE_BUSY)
    rig.run(100)
    assert rig.actual() == CELL_POSITION


def test_handling_while_moving_is_refused() -> None:
    rig = Rig(stock={CELL: "A"})
    rig.move(*CELL_POSITION)
    rig.run(1)
    rig.crane.pick_start = True
    rig.run(1)
    assert_fault(rig, FaultCode.CRANE_BUSY)
    assert not rig.crane.handling_active


def test_a_start_while_handling_is_refused_and_handling_finishes() -> None:
    rig = Rig()
    rig.plant.offer_load(1, "left", "A")
    rig.crane.pick_start = True
    rig.run(1)
    rig.move(2.0, 0.0)
    rig.run(1)
    assert_fault(rig, FaultCode.CRANE_BUSY)
    rig.run(100)
    assert rig.plant.load_on_crane(1) == "A"
    assert rig.actual() == (0.0, 0.0)


def test_handling_between_cells_is_refused() -> None:
    rig = Rig()
    go_to(rig, 5.0, 0.0)
    rig.crane.side = 1
    rig.crane.pick_start = True
    rig.run(1)
    assert_fault(rig, FaultCode.NO_PLACE)


def test_a_side_without_a_rack_is_refused() -> None:
    rig = Rig(stock={CELL: "A"})
    go_to(rig, *CELL_POSITION)
    rig.crane.side = 2
    rig.crane.pick_start = True
    rig.run(1)
    assert_fault(rig, FaultCode.INVALID_SIDE)
    assert loads(rig) == 1


def test_picking_from_an_empty_cell_creates_no_load() -> None:
    rig = Rig()
    go_to(rig, *CELL_POSITION)
    rig.crane.side = 1
    rig.crane.pick_start = True
    rig.run(200)
    assert_fault(rig, FaultCode.NOTHING_TO_PICK)
    assert loads(rig) == 0


def test_picking_at_an_inbound_end_with_nothing_offered_is_refused() -> None:
    rig = Rig()
    rig.crane.pick_start = True
    rig.run(1)
    assert_fault(rig, FaultCode.NOTHING_TO_PICK)


def test_picking_at_an_end_with_no_inbound_role_is_refused() -> None:
    rig = Rig()
    go_to(rig, *RIGHT_END)
    rig.crane.pick_start = True
    rig.run(1)
    assert_fault(rig, FaultCode.NOTHING_TO_PICK)


def test_setting_into_an_occupied_cell_loses_no_load() -> None:
    rig = Rig(stock={CELL: "A", (1, 1, 1, 1): "B"})
    picked(rig)
    go_to(rig, 2.0, 0.0)
    rig.crane.set_start = True
    rig.run(200)
    assert_fault(rig, FaultCode.PLACE_OCCUPIED)
    assert loads(rig) == 2
    assert rig.plant.cell_contents() == {(1, 1, 1, 1): "B"}
    assert rig.plant.load_on_crane(1) == "A"


def test_setting_at_an_end_with_no_outbound_role_is_refused() -> None:
    rig = Rig(stock={CELL: "A"})
    picked(rig)
    go_to(rig, 0.0, 0.0)
    rig.crane.set_start = True
    rig.run(1)
    assert_fault(rig, FaultCode.SET_NOT_ALLOWED)
    assert loads(rig) == 1


def test_picking_with_a_load_on_the_crane_is_refused() -> None:
    rig = Rig(stock={CELL: "A", (1, 1, 1, 1): "B"})
    picked(rig)
    go_to(rig, 2.0, 0.0)
    rig.crane.pick_start = True
    rig.run(200)
    assert_fault(rig, FaultCode.CRANE_ALREADY_LOADED)
    assert loads(rig) == 2


def test_setting_with_no_load_on_the_crane_is_refused() -> None:
    rig = Rig()
    go_to(rig, *CELL_POSITION)
    rig.crane.side = 1
    rig.crane.set_start = True
    rig.run(200)
    assert_fault(rig, FaultCode.CRANE_EMPTY)
    assert loads(rig) == 0


def test_pick_and_set_in_one_cycle_are_refused() -> None:
    rig = Rig()
    rig.plant.offer_load(1, "left", "A")
    rig.crane.pick_start = rig.crane.set_start = True
    rig.run(1)
    assert_fault(rig, FaultCode.CONFLICTING_COMMANDS)
    assert not rig.crane.handling_active


def test_fault_is_recorded_with_its_cycle_and_time() -> None:
    rig = Rig()
    go_to(rig, 5.0, 0.0)
    rig.crane.pick_start = True
    rig.run(1)
    fault = rig.plant.faults[0]
    assert fault.cycle == 130
    assert fault.time_s == 13.0
    assert "5.0" in fault.description


def test_commands_are_ignored_until_a_reset_clears_the_fault() -> None:
    rig = Rig()
    rig.move(99.0, 0.0)
    rig.run(1)
    rig.move(4.0, 0.0)
    rig.run(50)
    assert rig.actual() == (0.0, 0.0)
    assert rig.crane.fault_code == FaultCode.TARGET_OUT_OF_RANGE
    assert len(rig.plant.faults) == 1

    rig.crane.fault_reset = True
    rig.run(1)
    assert rig.crane.fault_code == 0
    rig.move(4.0, 0.0)
    rig.run(100)
    assert rig.actual() == (4.0, 0.0)


def test_holding_reset_true_clears_only_once() -> None:
    rig = Rig()
    rig.crane.fault_reset = True
    rig.run(1)
    rig.move(99.0, 0.0)
    rig.run(1)
    assert rig.crane.fault_code == FaultCode.TARGET_OUT_OF_RANGE
    rig.run(5)
    assert rig.crane.fault_code == FaultCode.TARGET_OUT_OF_RANGE


def test_a_fault_holds_only_the_affected_crane() -> None:
    content = minimal_warehouse_dict()
    content["layout"]["aisle_count"] = 2
    signals = {1: CraneSignals(), 2: CraneSignals()}
    plant = Plant(WarehouseDefinition.model_validate(content), 100, signals, Observer())
    signals[1].horizontal_target_m = 99.0
    signals[1].horizontal_start = True
    signals[2].horizontal_target_m = 2.0
    signals[2].horizontal_start = True
    for cycle in range(40):
        plant.advance(cycle)
    assert signals[1].fault_code == FaultCode.TARGET_OUT_OF_RANGE
    assert signals[2].fault_code == 0
    assert signals[2].horizontal_actual_m == 2.0
