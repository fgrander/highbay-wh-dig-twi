"""The steps of the start of a run, as in contracts/plc-interface.md."""

from collections.abc import Callable

import pytest

from data.memory_plc import MemoryPlc
from highbay_sim.plc.controller import PlcController, PlcRefused
from highbay_sim.plc.interface import (
    CRANE_COUNT_TAG,
    HEARTBEAT_TAG,
    INTERFACE_VERSION_TAG,
    RESET_REQUEST_TAG,
    SIGNAL_LIST_VERSION_TAG,
    PlcInterface,
)

INTERFACE = PlcInterface(2)


def controller_for(plc: MemoryPlc) -> PlcController:
    return PlcController(plc, plc.interface, 50, clock=plc.now, wait=plc.wait)


def test_a_good_plc_is_prepared() -> None:
    plc = MemoryPlc(INTERFACE)
    controller = controller_for(plc)
    controller.prepare()
    assert controller.state == "prepared"
    assert not plc.closed
    controller.close()
    assert plc.closed


def test_the_steps_run_in_the_order_of_the_contract() -> None:
    calls: list[str] = []
    plc = MemoryPlc(INTERFACE)

    def traced(name: str, method: Callable[..., object]) -> Callable[..., object]:
        def call(*arguments: object) -> object:
            calls.append(name)
            return method(*arguments)

        return call

    plc.device_string = traced("identity", plc.device_string)  # type: ignore[method-assign]
    plc.cpu_state = traced("state", plc.cpu_state)  # type: ignore[method-assign]
    plc.tag_types = traced("types", plc.tag_types)  # type: ignore[method-assign]
    plc.read = traced("read", plc.read)  # type: ignore[method-assign]
    plc.write = traced("write", plc.write)  # type: ignore[method-assign]
    controller_for(plc).prepare()
    assert calls[:3] == ["identity", "state", "types"]
    assert calls[3] == "read"
    assert "write" in calls
    first_write = calls.index("write")
    assert "identity" not in calls[first_write:]
    assert calls[-1] == "write"


def test_a_plc_not_in_run_is_refused() -> None:
    plc = MemoryPlc(INTERFACE)
    plc.state = "STOP"
    with pytest.raises(PlcRefused, match="STOP"):
        controller_for(plc).prepare()
    assert plc.write_requests == []
    assert plc.closed


def test_all_differences_are_named_at_once() -> None:
    plc = MemoryPlc(INTERFACE)
    plc.overrides["HB_Interface.crane_1.job_id"] = None
    plc.overrides["HB_Interface.crane_2.side"] = "Int"
    with pytest.raises(PlcRefused) as refused:
        controller_for(plc).prepare()
    assert "HB_Interface.crane_1.job_id" in str(refused.value)
    assert "HB_Interface.crane_2.side" in str(refused.value)
    assert "Int" in str(refused.value)
    assert plc.write_requests == []
    assert plc.closed


def test_differing_start_values_are_all_named() -> None:
    plc = MemoryPlc(INTERFACE)
    plc.tags[INTERFACE_VERSION_TAG] = 99
    plc.tags[SIGNAL_LIST_VERSION_TAG] = 98
    plc.tags[CRANE_COUNT_TAG] = 97
    with pytest.raises(PlcRefused) as refused:
        controller_for(plc).prepare()
    for text in ("interface_version", "signal_list_version", "crane_count", "99", "98", "97"):
        assert text in str(refused.value)
    assert plc.write_requests == []


def test_a_heartbeat_that_does_not_change_within_2_s_is_refused() -> None:
    plc = MemoryPlc(INTERFACE)
    plc.heartbeat_frozen = True
    with pytest.raises(PlcRefused, match="heartbeat"):
        controller_for(plc).prepare()
    assert plc.write_requests == []
    assert 2.0 <= plc.now() < 2.1


def test_no_reset_done_within_5_s_is_refused() -> None:
    plc = MemoryPlc(INTERFACE)
    plc.reset_ignored = True
    with pytest.raises(PlcRefused, match="reset_done"):
        controller_for(plc).prepare()
    assert plc.closed
    assert 5.0 <= plc.now() < 5.1


def test_values_from_an_earlier_run_are_gone() -> None:
    plc = MemoryPlc(INTERFACE)
    interface = plc.interface
    plc.tags[interface.tag(1, "job_id")] = 7
    plc.tags[interface.tag(1, "horizontal_actual_m")] = 9.5
    plc.tags[interface.tag(1, "job_done_id")] = 6
    plc.tags[interface.tag(1, "pick_start")] = True
    controller_for(plc).prepare()
    assert plc.tags[interface.tag(1, "job_id")] == 0
    assert plc.tags[interface.tag(1, "horizontal_actual_m")] == 0.0
    assert plc.tags[interface.tag(1, "job_done_id")] == 0
    assert plc.tags[interface.tag(1, "pick_start")] is False


def test_the_reset_request_comes_first_and_is_cleared() -> None:
    plc = MemoryPlc(INTERFACE)
    controller_for(plc).prepare()
    assert plc.write_requests[0] == {RESET_REQUEST_TAG: True}
    assert set(plc.write_requests[1]) == set(plc.interface.model_tags)
    assert plc.write_requests[-1] == {RESET_REQUEST_TAG: False}
    assert plc.tags[RESET_REQUEST_TAG] is False


def test_a_failed_request_during_the_start_refuses_and_closes() -> None:
    plc = MemoryPlc(INTERFACE)
    plc.fail_on_request = 1
    with pytest.raises(PlcRefused, match="lost"):
        controller_for(plc).prepare()
    assert plc.closed


def test_the_heartbeat_is_read_at_least_twice() -> None:
    plc = MemoryPlc(INTERFACE)
    before = plc.tags[HEARTBEAT_TAG]
    controller_for(plc).prepare()
    assert plc.tags[HEARTBEAT_TAG] != before


def test_a_refused_controller_cannot_exchange() -> None:
    plc = MemoryPlc(INTERFACE)
    plc.state = "STOP"
    controller = controller_for(plc)
    with pytest.raises(PlcRefused):
        controller.prepare()
    assert controller.state == "refused"
    with pytest.raises(RuntimeError):
        controller.scan({})
    assert plc.write_requests == []


def test_a_controller_that_was_not_prepared_cannot_exchange() -> None:
    plc = MemoryPlc(INTERFACE)
    with pytest.raises(RuntimeError):
        controller_for(plc).scan({})
    assert plc.write_requests == []


def test_closing_twice_is_harmless() -> None:
    plc = MemoryPlc(INTERFACE)
    controller = controller_for(plc)
    controller.close()
    controller.close()
    assert plc.closed
