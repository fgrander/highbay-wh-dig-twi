"""The exchange in each cycle, with the PLC's own time in place of the system clock."""

import signal

import pytest

from data.memory_plc import MemoryPlc
from highbay_sim.controller import ControllerStopped
from highbay_sim.plc.controller import PlcController
from highbay_sim.plc.interface import PlcInterface
from highbay_sim.signals import CraneSignals

INTERFACE = PlcInterface(2)


def prepared(plc: MemoryPlc | None = None) -> tuple[MemoryPlc, PlcController]:
    plc = MemoryPlc(INTERFACE) if plc is None else plc
    controller = PlcController(plc, plc.interface, 50, clock=plc.now, wait=plc.wait)
    controller.prepare()
    plc.write_requests.clear()
    return plc, controller


def cranes() -> dict[int, CraneSignals]:
    return {aisle: CraneSignals() for aisle in INTERFACE.aisles}


def test_only_changed_tags_are_written() -> None:
    plc, controller = prepared()
    signals = cranes()
    controller.scan(signals)
    assert plc.write_requests == []
    signals[1].horizontal_actual_m = 1.5
    controller.scan(signals)
    assert plc.write_requests == [{INTERFACE.tag(1, "horizontal_actual_m"): 1.5}]
    controller.scan(signals)
    assert len(plc.write_requests) == 1


def test_a_changed_job_id_is_written_afterwards_in_a_request_of_its_own() -> None:
    plc, controller = prepared()
    signals = cranes()
    signals[1].source_horizontal_m = 3.0
    signals[1].job_id = 1
    signals[2].job_id = 4
    controller.scan(signals)
    assert plc.write_requests[0] == {INTERFACE.tag(1, "source_horizontal_m"): 3.0}
    assert plc.write_requests[1:] == [
        {INTERFACE.tag(1, "job_id"): 1},
        {INTERFACE.tag(2, "job_id"): 4},
    ]


def test_no_tag_of_the_plc_is_ever_written() -> None:
    plc, controller = prepared()
    signals = cranes()
    for crane in signals.values():
        crane.pick_start = True
        crane.job_done_id = 9
        crane.horizontal_target_m = 2.0
    controller.scan(signals)
    written = {name for request in plc.write_requests for name in request}
    assert written.isdisjoint(INTERFACE.plc_tags)


def test_commands_that_are_read_reach_the_signals() -> None:
    plc, controller = prepared()
    plc.tags[INTERFACE.tag(2, "pick_start")] = True
    plc.tags[INTERFACE.tag(2, "side")] = 2
    plc.tags[INTERFACE.tag(2, "horizontal_target_m")] = 4.5
    plc.tags[INTERFACE.tag(2, "job_done_id")] = 3
    signals = cranes()
    controller.scan(signals)
    assert signals[2].pick_start is True
    assert signals[2].side == 2
    assert signals[2].horizontal_target_m == 4.5
    assert signals[2].job_done_id == 3
    assert signals[1].pick_start is False


def test_a_cycle_within_its_time_waits_for_its_deadline() -> None:
    plc, controller = prepared()
    signals = cranes()
    started = plc.now()
    for _ in range(4):
        controller.scan(signals)
    assert plc.now() == pytest.approx(started + 0.2)
    assert controller.stats().overrun_cycles == 0
    assert controller.stats().cycles == 4


def test_a_cycle_longer_than_the_cycle_time_counts_as_an_overrun_and_none_is_skipped() -> None:
    plc, controller = prepared()
    signals = cranes()
    plc.latency_s = 0.06
    for _ in range(3):
        controller.scan(signals)
    stats = controller.stats()
    assert stats.cycles == 3
    assert stats.overrun_cycles == 3
    assert stats.slowest_exchange_ms == pytest.approx(60.0)
    assert stats.real_s > stats.simulated_s


def test_time_outside_the_scan_counts_towards_the_cycle() -> None:
    plc, controller = prepared()
    signals = cranes()
    controller.scan(signals)
    plc.wait(0.08)
    controller.scan(signals)
    assert controller.stats().overrun_cycles == 1


def test_a_slower_cycle_does_not_make_later_ones_overrun() -> None:
    plc, controller = prepared()
    signals = cranes()
    controller.scan(signals)
    plc.wait(0.08)
    controller.scan(signals)
    controller.scan(signals)
    controller.scan(signals)
    assert controller.stats().overrun_cycles == 1


def test_a_failed_read_stops_with_connection_lost_and_is_not_retried() -> None:
    plc, controller = prepared()
    signals = cranes()
    controller.scan(signals)
    plc.fail_on_request = plc.requests + 1
    requests = plc.requests
    with pytest.raises(ControllerStopped) as stopped:
        controller.scan(signals)
    assert stopped.value.reason == "connection_lost"
    assert plc.requests == requests + 1
    assert controller.stats().stop_reason == "connection_lost"
    assert controller.stats().stopped_at_cycle == 1


def test_a_failed_write_stops_and_is_not_retried() -> None:
    plc, controller = prepared()
    signals = cranes()
    signals[1].job_id = 1
    plc.fail_on_request = plc.requests + 1
    with pytest.raises(ControllerStopped) as stopped:
        controller.scan(signals)
    assert stopped.value.reason == "connection_lost"
    assert plc.write_requests == []


def test_a_heartbeat_unchanged_for_2_s_stops_with_plc_not_running() -> None:
    plc, controller = prepared()
    signals = cranes()
    controller.scan(signals)
    plc.state = "STOP"
    started = plc.now()
    with pytest.raises(ControllerStopped) as stopped:
        for _ in range(100):
            controller.scan(signals)
    assert stopped.value.reason == "plc_not_running"
    assert plc.now() - started == pytest.approx(2.0, abs=0.1)


def test_a_slow_exchange_alone_does_not_stop_the_run() -> None:
    plc, controller = prepared()
    plc.latency_s = 0.5
    signals = cranes()
    for _ in range(5):
        controller.scan(signals)
    assert controller.stats().stop_reason == "finished"


def test_sigint_stops_with_interrupted_at_the_next_scan() -> None:
    plc, controller = prepared()
    signals = cranes()
    controller.scan(signals)
    signal.raise_signal(signal.SIGINT)
    writes = plc.requests
    with pytest.raises(ControllerStopped) as stopped:
        controller.scan(signals)
    assert stopped.value.reason == "interrupted"
    assert plc.requests == writes
    controller.close()


def test_the_interrupt_handler_is_restored_at_the_close() -> None:
    before = signal.getsignal(signal.SIGINT)
    _, controller = prepared()
    assert signal.getsignal(signal.SIGINT) is not before
    controller.close()
    assert signal.getsignal(signal.SIGINT) is before


def test_nothing_is_written_after_a_stop() -> None:
    plc, controller = prepared()
    signals = cranes()
    controller.scan(signals)
    plc.fail_on_request = plc.requests + 1
    with pytest.raises(ControllerStopped):
        controller.scan(signals)
    plc.fail_on_request = None
    plc.write_requests.clear()
    signals[1].job_id = 9
    with pytest.raises(ControllerStopped):
        controller.scan(signals)
    assert plc.write_requests == []


def test_the_end_of_a_run_writes_nothing_and_closes() -> None:
    plc, controller = prepared()
    signals = cranes()
    controller.scan(signals)
    plc.write_requests.clear()
    controller.close()
    assert plc.write_requests == []
    assert plc.closed


def test_the_stats_describe_the_run() -> None:
    plc, controller = prepared()
    signals = cranes()
    for _ in range(11):
        controller.scan(signals)
    stats = controller.stats()
    assert stats.device == plc.device
    assert stats.interface_version == 1
    assert stats.stop_reason == "finished"
    assert stats.stopped_at_cycle is None
    assert stats.cycles == 11
    assert stats.simulated_s == pytest.approx(0.5)
    assert stats.real_s == pytest.approx(0.55)
    assert stats.overrun_cycles == 0
