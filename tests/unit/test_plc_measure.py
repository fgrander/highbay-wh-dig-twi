"""The measurement of the exchange. These figures say nothing about a real S7-PLCSIM Advanced."""

import pytest

from data.memory_plc import MemoryPlc
from highbay_sim.controller import ControllerStopped
from highbay_sim.plc.controller import PlcController, PlcRefused
from highbay_sim.plc.interface import PlcInterface
from highbay_sim.plc.measure import measure, percentile


def controller_for(plc: MemoryPlc) -> PlcController:
    return PlcController(plc, plc.interface, 50, clock=plc.now, wait=plc.wait)


def test_percentile_uses_the_nearest_rank() -> None:
    values = sorted(float(value) for value in range(1, 101))
    assert percentile(values, 50) == 50.0
    assert percentile(values, 99) == 99.0
    assert percentile(values, 100) == 100.0
    assert percentile([7.0], 99) == 7.0


def test_figures_come_from_the_given_exchange_times() -> None:
    plc = MemoryPlc(PlcInterface(1), latency_s=0.004)
    result = measure(controller_for(plc), plc.interface, 50, 5.0)
    assert result.device == plc.device
    assert result.crane_count == 1
    assert result.cycles == 100
    assert result.overrun_cycles == 0
    # Each cycle writes the two positions, and then reads: two requests.
    assert result.median_ms == pytest.approx(8.0)
    assert result.p99_ms == pytest.approx(8.0)
    assert result.slowest_ms == pytest.approx(8.0)


def test_slow_exchanges_count_as_overruns() -> None:
    plc = MemoryPlc(PlcInterface(1), latency_s=0.03)
    result = measure(controller_for(plc), plc.interface, 50, 3.0)
    assert result.overrun_cycles == result.cycles
    assert result.slowest_ms == pytest.approx(60.0)


def test_a_refused_device_receives_no_write() -> None:
    plc = MemoryPlc(PlcInterface(1), device="1;6ES7 511-1AK02-0AB0;V2.9")
    with pytest.raises(PlcRefused):
        measure(controller_for(plc), plc.interface, 50, 1.0)
    assert plc.write_requests == []


def test_no_job_starts() -> None:
    plc = MemoryPlc(PlcInterface(2))
    measure(controller_for(plc), plc.interface, 50, 1.0)
    written = {name for request in plc.write_requests for name in request}
    assert "HB_Interface.crane_1.horizontal_actual_m" in written
    jobs = [
        request[name]
        for request in plc.write_requests
        for name in request
        if name.endswith(".job_id")
    ]
    assert not any(jobs)
    assert plc.tags["HB_Interface.crane_1.horizontal_start"] is False


def test_a_lost_connection_ends_the_measurement() -> None:
    plc = MemoryPlc(PlcInterface(1))
    controller = controller_for(plc)
    plc.fail_on_request = 200
    with pytest.raises(ControllerStopped):
        measure(controller, plc.interface, 50, 60.0)


def test_the_text_names_the_device_and_the_limit_of_the_figures() -> None:
    plc = MemoryPlc(PlcInterface(1))
    text = measure(controller_for(plc), plc.interface, 50, 1.0).text()
    assert plc.device is not None
    assert plc.device in text
    for word in ("median", "99th percentile", "slowest", "Overruns"):
        assert word in text
    assert "this connection" in text
