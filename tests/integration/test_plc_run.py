"""Whole runs through the in-memory PLC. They do not exercise the real connection."""

import pytest

from conftest import minimal_warehouse_dict
from data.memory_plc import MemoryPlc
from highbay_sim.config import WarehouseDefinition
from highbay_sim.controller import Controller
from highbay_sim.metrics import calculate_metrics
from highbay_sim.orders import ExplicitOrders, OrderRequest
from highbay_sim.outputs import Execution, RunInfo, report_text, result_document
from highbay_sim.plc.controller import PlcController
from highbay_sim.plc.interface import PlcInterface
from highbay_sim.signals import SIGNAL_LIST_VERSION, FaultCode
from highbay_sim.stepped import SteppedRun, simulate_stepped

CYCLE_MS = 50
ORDERS = [
    (0.0, "storage", "A"),
    (1.0, "storage", "A"),
    (2.0, "storage", "B"),
    (120.0, "retrieval", "A"),
    (121.0, "retrieval", "B"),
    (122.0, "retrieval", "A"),
]


def warehouse(crane_count: int = 1) -> WarehouseDefinition:
    document = minimal_warehouse_dict()
    document["layout"]["aisle_count"] = crane_count
    return WarehouseDefinition.model_validate(document)


def run_with(
    controller: Controller | None,
    crane_count: int = 1,
    duration_s: float = 400.0,
    orders: tuple[tuple[float, str, str], ...] | list[tuple[float, str, str]] = ORDERS,
) -> SteppedRun:
    source = ExplicitOrders([OrderRequest(*order) for order in orders])  # type: ignore[arg-type]
    return simulate_stepped(warehouse(crane_count), source, 1, duration_s, CYCLE_MS, controller)


def plc_controller(plc: MemoryPlc) -> PlcController:
    controller = PlcController(plc, plc.interface, CYCLE_MS, clock=plc.now, wait=plc.wait)
    controller.prepare()
    return controller


def total_time(run: SteppedRun) -> float:
    return max(order.completion_s or 0.0 for order in run.record.orders)


@pytest.mark.parametrize(("crane_count", "scan_ms"), [(1, 7.0), (1, 23.0), (2, 11.0)])
def test_finishes_the_same_orders_in_a_similar_time(crane_count: int, scan_ms: float) -> None:
    built_in = run_with(None, crane_count)
    plc = MemoryPlc(PlcInterface(crane_count), CYCLE_MS, scan_ms)
    under_plc = run_with(plc_controller(plc), crane_count)
    finished = [(order.order_id, order.outcome, order.location) for order in built_in.record.orders]
    assert finished == [
        (order.order_id, order.outcome, order.location) for order in under_plc.record.orders
    ]
    assert all(order.outcome == "completed" for order in under_plc.record.orders)
    assert under_plc.faults == ()
    assert total_time(under_plc) == pytest.approx(total_time(built_in), rel=0.05)
    assert total_time(under_plc) > total_time(built_in)


def test_a_slow_exchange_still_finishes_the_same_orders() -> None:
    plc = MemoryPlc(PlcInterface(1), CYCLE_MS, 7.0, latency_s=0.02)
    run = run_with(plc_controller(plc))
    assert all(order.outcome == "completed" for order in run.record.orders)


def test_a_command_that_the_plant_refuses_gives_the_fault_code_of_the_signal_list() -> None:
    plc = MemoryPlc(PlcInterface(1), CYCLE_MS)
    controller = plc_controller(plc)
    target = plc.interface.tag(1, "horizontal_target_m")
    start = plc.interface.tag(1, "horizontal_start")

    class Wrong:
        def scan(self, signals: object) -> None:
            plc.tags[target] = 1e6
            plc.tags[start] = True
            controller.scan(signals)  # type: ignore[arg-type]

    run = run_with(Wrong(), duration_s=1.0, orders=[])
    assert [fault.code for fault in run.faults] == [FaultCode.TARGET_OUT_OF_RANGE]


def test_nothing_new_starts_during_a_fault() -> None:
    plc = MemoryPlc(PlcInterface(1), CYCLE_MS)
    controller = plc_controller(plc)
    started: list[bool] = []

    class Faulted:
        def scan(self, signals: dict) -> None:  # type: ignore[type-arg]
            signals[1].fault_code = int(FaultCode.CRANE_BUSY)
            controller.scan(signals)
            crane = signals[1]
            started.append(crane.horizontal_start or crane.pick_start or crane.set_start)

    run_with(Faulted(), duration_s=2.0)
    assert not any(started)


def test_a_connection_lost_mid_run_keeps_what_was_recorded() -> None:
    plc = MemoryPlc(PlcInterface(1), CYCLE_MS)
    controller = plc_controller(plc)
    plc.fail_on_request = plc.requests + 1000
    run = run_with(controller)
    assert run.stop is not None
    assert run.stop.reason == "connection_lost"
    assert run.stop.cycle > 0
    assert run.record.duration_s == pytest.approx(run.stop.cycle * CYCLE_MS / 1000)
    assert run.record.events
    metrics = calculate_metrics(run.record, 0.0)
    assert metrics.throughput_total >= 0.0
    assert controller.stats().stop_reason == "connection_lost"


def test_the_plc_section_appears_only_in_plc_runs_and_states_the_facts() -> None:
    plc = MemoryPlc(PlcInterface(1), CYCLE_MS)
    controller = plc_controller(plc)
    run = run_with(controller, duration_s=10.0)
    stats = controller.stats()
    metrics = calculate_metrics(run.record, 0.0)
    section = stats.report()
    execution = Execution(CYCLE_MS, "plc", None, SIGNAL_LIST_VERSION, section)
    info = RunInfo("1", 1, "w", "x", "s", "y", 10.0, execution)
    result = result_document(info, metrics)
    assert result["plc"] == {
        "device": "1;6ES7 SIM-01500-APLC;S4.1",
        "interface_version": 1,
        "reproducible": False,
        "stop_reason": "finished",
        "stopped_at_cycle": None,
        "cycles": 201,
        "overrun_cycles": 0,
        "slowest_exchange_ms": pytest.approx(0.0, abs=1.0),
        "simulated_s": 10.0,
        "real_s": pytest.approx(10.05),
    }
    report = report_text(info, result)
    assert "not reproducible" in report
    assert "1;6ES7 SIM-01500-APLC;S4.1" in report
    assert "Overrun cycles: 0" in report
    assert "Slowest exchange" in report
    plain = Execution(CYCLE_MS, "built-in", None, SIGNAL_LIST_VERSION)
    plain_result = result_document(RunInfo("1", 1, "w", "x", "s", "y", 10.0, plain), metrics)
    assert "plc" not in plain_result
