"""An in-memory stand-in for a simulated PLC with the generated program.

This is a Python copy of the logic that the generator writes as SCL. A test that passes with it says
nothing about the real connection, or about how the SCL behaves.

It has its own time. Its program runs every scan_ms of that time, not aligned with the model's
cycles, and `now` and `wait` take the place of the system clock.
"""

from collections.abc import Callable
from enum import Enum, auto

from highbay_sim.controller import POSITION_TOLERANCE_M
from highbay_sim.plc.interface import (
    CRANE_COUNT_TAG,
    HEARTBEAT_TAG,
    INTERFACE_VERSION,
    INTERFACE_VERSION_TAG,
    PLC_SIGNALS,
    RESET_DONE_TAG,
    RESET_REQUEST_TAG,
    SIGNAL_LIST_VERSION_TAG,
    PlcInterface,
)
from highbay_sim.plc.link import LinkError, PlcValue
from highbay_sim.plc.source import HOLD_CYCLES
from highbay_sim.signals import SIGNAL_LIST_VERSION

SIMULATED_DEVICE = "1;6ES7 SIM-01500-APLC;S4.1"
_STARTS = ("horizontal_start", "vertical_start", "pick_start", "set_start")


class _State(Enum):
    IDLE = auto()
    TO_SOURCE = auto()
    PICKING = auto()
    TO_DESTINATION = auto()
    SETTING = auto()


class _Phase(Enum):
    READY = auto()
    SETTLE = auto()
    HOLD_ON = auto()
    HOLD_OFF = auto()


class _Crane:
    def __init__(self) -> None:
        self.state = _State.IDLE
        self.phase = _Phase.READY
        self.elapsed_s = 0.0
        self.starts: tuple[str, ...] = ()
        self.job: dict[str, PlcValue] = {}
        self.job_id: PlcValue = 0


class MemoryPlc:
    def __init__(
        self,
        interface: PlcInterface,
        cycle_ms: int = 50,
        scan_ms: float = 7.0,
        device: str | None = SIMULATED_DEVICE,
        latency_s: float = 0.0,
    ) -> None:
        self.interface = interface
        self.cycle_s = cycle_ms / 1000
        self.scan_s = scan_ms / 1000
        self.device = device
        self.latency_s = latency_s
        self.state = "RUN"
        self.heartbeat_frozen = False
        self.reset_ignored = False
        self.fail_on_request: int | None = None
        self.identity_error: Exception | None = None
        self.overrides: dict[str, str | None] = {}
        self.write_requests: list[dict[str, PlcValue]] = []
        self.requests = 0
        self.closed = False
        self.on_wait: Callable[[], None] | None = None
        self._now = 0.0
        self._next_scan = self.scan_s
        self._types = interface.tag_types()
        self.tags: dict[str, PlcValue] = {
            name: 0.0 if kind == "LReal" else 0 if kind == "DInt" else False
            for name, kind in self._types.items()
        }
        self.tags[INTERFACE_VERSION_TAG] = INTERFACE_VERSION
        self.tags[SIGNAL_LIST_VERSION_TAG] = SIGNAL_LIST_VERSION
        self.tags[CRANE_COUNT_TAG] = interface.crane_count
        self._cranes = {aisle: _Crane() for aisle in interface.aisles}

    # The time of this PLC, in place of the system clock.

    def now(self) -> float:
        return self._now

    def wait(self, seconds: float) -> None:
        self._pass(max(seconds, 0.0))
        if self.on_wait is not None:
            self.on_wait()

    def _pass(self, seconds: float) -> None:
        end = self._now + seconds
        while self._next_scan <= end:
            self._now = self._next_scan
            self._next_scan += self.scan_s
            if self.state == "RUN":
                self._scan()
        self._now = end

    # TagLink

    def device_string(self) -> str | None:
        if self.identity_error is not None:
            raise self.identity_error
        return self.device

    def cpu_state(self) -> str:
        return self.state

    def tag_types(self, names: list[str]) -> dict[str, str | None]:
        known: dict[str, str | None] = {name: self._types.get(name) for name in names}
        return known | {name: kind for name, kind in self.overrides.items() if name in known}

    def read(self, names: list[str]) -> list[PlcValue]:
        self._request()
        return [self.tags[name] for name in names]

    def write(self, values: dict[str, PlcValue]) -> None:
        self._request()
        self.write_requests.append(dict(values))
        for name, value in values.items():
            kind = self._types[name]
            valid = (
                isinstance(value, bool)
                if kind == "Bool"
                else not isinstance(value, bool) and isinstance(value, int | float)
            )
            if not valid:
                raise LinkError(f"{value!r} is not a value of type {kind}")
            self.tags[name] = value

    def close(self) -> None:
        self.closed = True

    def _request(self) -> None:
        if self.closed:
            raise LinkError("the link is closed")
        self.requests += 1
        if self.fail_on_request is not None and self.requests >= self.fail_on_request:
            raise LinkError("the connection was lost")
        self._pass(self.latency_s)

    # The program.

    def _scan(self) -> None:
        if not self.heartbeat_frozen:
            self.tags[HEARTBEAT_TAG] = int(self.tags[HEARTBEAT_TAG]) + 1
        resetting = bool(self.tags[RESET_REQUEST_TAG]) and not self.reset_ignored
        for aisle, crane in self._cranes.items():
            if resetting:
                self._reset(aisle, crane)
            else:
                self._control(aisle, crane)
        self.tags[RESET_DONE_TAG] = resetting

    def _reset(self, aisle: int, crane: _Crane) -> None:
        self._cranes[aisle] = _Crane()
        for signal in PLC_SIGNALS:
            name = self.interface.tag(aisle, signal.name)
            kind = self._types[name]
            self.tags[name] = 0.0 if kind == "LReal" else 0 if kind == "DInt" else False

    def _get(self, aisle: int, signal: str) -> PlcValue:
        return self.tags[self.interface.tag(aisle, signal)]

    def _set(self, aisle: int, signal: str, value: PlcValue) -> None:
        self.tags[self.interface.tag(aisle, signal)] = value

    def _control(self, aisle: int, crane: _Crane) -> None:
        if crane.phase is not _Phase.READY:
            self._advance_phase(aisle, crane)
            return
        if self._get(aisle, "fault_code"):
            return
        state = crane.state
        if state is _State.IDLE:
            job_id = self._get(aisle, "job_id")
            if job_id != self._get(aisle, "job_done_id"):
                crane.job_id = job_id
                crane.job = {
                    name: self._get(aisle, name)
                    for name in (
                        "source_horizontal_m",
                        "source_vertical_m",
                        "source_side",
                        "destination_horizontal_m",
                        "destination_vertical_m",
                        "destination_side",
                    )
                }
                self._go(aisle, crane, "source", _State.TO_SOURCE, _State.PICKING)
        elif state is _State.TO_SOURCE:
            if self._in_position(aisle):
                self._handle(aisle, crane, "source", "pick_start", _State.PICKING)
        elif state is _State.PICKING:
            if self._get(aisle, "load_present"):
                self._go(aisle, crane, "destination", _State.TO_DESTINATION, _State.SETTING)
        elif state is _State.TO_DESTINATION:
            if self._in_position(aisle):
                self._handle(aisle, crane, "destination", "set_start", _State.SETTING)
        elif not self._get(aisle, "load_present"):
            self._set(aisle, "job_done_id", crane.job_id)
            crane.state = _State.IDLE

    def _in_position(self, aisle: int) -> bool:
        return bool(self._get(aisle, "horizontal_in_position")) and bool(
            self._get(aisle, "vertical_in_position")
        )

    def _go(self, aisle: int, crane: _Crane, place: str, moving: _State, handling: _State) -> None:
        horizontal = float(crane.job[f"{place}_horizontal_m"])
        vertical = float(crane.job[f"{place}_vertical_m"])
        at_place = (
            abs(float(self._get(aisle, "horizontal_actual_m")) - horizontal) <= POSITION_TOLERANCE_M
            and abs(float(self._get(aisle, "vertical_actual_m")) - vertical) <= POSITION_TOLERANCE_M
        )
        if at_place:
            start = "pick_start" if handling is _State.PICKING else "set_start"
            self._handle(aisle, crane, place, start, handling)
            return
        self._set(aisle, "horizontal_target_m", horizontal)
        self._set(aisle, "vertical_target_m", vertical)
        self._begin(crane, ("horizontal_start", "vertical_start"), moving)

    def _handle(self, aisle: int, crane: _Crane, place: str, start: str, handling: _State) -> None:
        self._set(aisle, "side", crane.job[f"{place}_side"])
        self._begin(crane, (start,), handling)

    def _begin(self, crane: _Crane, starts: tuple[str, ...], state: _State) -> None:
        crane.state = state
        crane.starts = starts
        crane.phase = _Phase.SETTLE
        crane.elapsed_s = 0.0

    def _advance_phase(self, aisle: int, crane: _Crane) -> None:
        crane.elapsed_s += self.scan_s
        hold_s = HOLD_CYCLES * self.cycle_s
        if crane.phase is _Phase.SETTLE and crane.elapsed_s >= self.cycle_s:
            for start in crane.starts:
                self._set(aisle, start, True)
            crane.phase, crane.elapsed_s = _Phase.HOLD_ON, 0.0
        elif crane.phase is _Phase.HOLD_ON and crane.elapsed_s >= hold_s:
            for start in _STARTS:
                self._set(aisle, start, False)
            crane.phase, crane.elapsed_s = _Phase.HOLD_OFF, 0.0
        elif crane.phase is _Phase.HOLD_OFF and crane.elapsed_s >= hold_s:
            crane.phase = _Phase.READY
