"""A simulated PLC as the controller of a time-stepped run, as in contracts/plc-interface.md.

Nothing can be written before the identity check has passed, and no option turns it off. This is the
only module that writes to a link.
"""

import contextlib
import signal
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import FrameType
from typing import Any, Final, NoReturn

from highbay_sim.controller import ControllerStopped
from highbay_sim.plc.interface import (
    CRANE_COUNT_TAG,
    HEARTBEAT_TAG,
    INTERFACE_VERSION,
    INTERFACE_VERSION_TAG,
    MODEL_SIGNALS,
    PLC_SIGNALS,
    RESET_DONE_TAG,
    RESET_REQUEST_TAG,
    SIGNAL_LIST_VERSION_TAG,
    PlcInterface,
)
from highbay_sim.plc.link import LinkError, PlcValue, TagLink, confirm_simulated
from highbay_sim.signals import SIGNAL_LIST_VERSION, CraneSignals

HEARTBEAT_LIMIT_S: Final = 2.0
RESET_LIMIT_S: Final = 5.0
POLL_S: Final = 0.02


class PlcRefused(Exception):
    """A step of the start of a run failed, so the run does not start."""


@dataclass(frozen=True)
class PlcRunStats:
    device: str
    interface_version: int
    stop_reason: str
    stopped_at_cycle: int | None
    cycles: int
    overrun_cycles: int
    slowest_exchange_ms: float
    simulated_s: float
    real_s: float

    def report(self) -> dict[str, Any]:
        """The plc section of result.json."""
        return {
            "device": self.device,
            "interface_version": self.interface_version,
            "reproducible": False,
            "stop_reason": self.stop_reason,
            "stopped_at_cycle": self.stopped_at_cycle,
            "cycles": self.cycles,
            "overrun_cycles": self.overrun_cycles,
            "slowest_exchange_ms": round(self.slowest_exchange_ms, 3),
            "simulated_s": round(self.simulated_s, 6),
            "real_s": round(self.real_s, 3),
        }


class PlcController:
    """A Controller, so the cycle loop does not need to know about PLCs."""

    def __init__(
        self,
        link: TagLink,
        interface: PlcInterface,
        cycle_ms: int,
        clock: Callable[[], float] = time.monotonic,
        wait: Callable[[float], None] = time.sleep,
    ) -> None:
        self.state = "created"
        self.last_exchange_ms = 0.0
        self._link = link
        self._interface = interface
        self._cycle_s = cycle_ms / 1000
        self._clock = clock
        self._wait = wait
        self._device = ""
        self._written: dict[str, PlcValue] = {}
        self._model_tags = [
            (aisle, definition.name, interface.tag(aisle, definition.name))
            for aisle in interface.aisles
            for definition in MODEL_SIGNALS
        ]
        self._plc_tags = [
            (aisle, definition.name, interface.tag(aisle, definition.name))
            for aisle in interface.aisles
            for definition in PLC_SIGNALS
        ]
        self._read_names = [tag for _, _, tag in self._plc_tags] + [HEARTBEAT_TAG]
        self._cycle = -1
        self._exchanges = 0
        self._overruns = 0
        self._slowest_ms = 0.0
        self._started_at = 0.0
        self._ended_at = 0.0
        self._cycle_start = 0.0
        self._heartbeat: PlcValue = 0
        self._heartbeat_changed_at = 0.0
        self._stop_reason = "finished"
        self._stop_message = ""
        self._interrupted = False
        self._previous_handler: Any = None
        self._handler_installed = False
        self._closed = False

    @property
    def device(self) -> str:
        return self._device

    # The start of a run.

    def prepare(self) -> None:
        """Carry out the steps of the start of a run. Any failure closes the link."""
        if self.state != "created":
            raise RuntimeError(f"a controller in state {self.state} cannot be prepared")
        try:
            self._check_identity()
            self._check_state()
            self._check_interface()
            self._check_heartbeat()
            self._reset()
        except LinkError as error:
            self._refuse()
            raise PlcRefused(f"the start of the run failed: {error}") from error
        except BaseException:
            self._refuse()
            raise
        self.state = "prepared"
        self._install_interrupt_handler()

    def _refuse(self) -> None:
        self.state = "refused"
        self.close()

    def _check_identity(self) -> None:
        # Nothing has been written before this check, and any doubt refuses the device.
        try:
            device = self._link.device_string()
        except Exception as error:
            raise PlcRefused(f"the identity of the device is unknown: {error}") from error
        if not confirm_simulated(device):
            shown = "an unknown device" if not device else f"device {device!r}"
            raise PlcRefused(f"{shown} is not confirmed as a simulated PLC, and is refused")
        assert device is not None
        self._device = device

    def _check_state(self) -> None:
        state = self._link.cpu_state()
        if state != "RUN":
            raise PlcRefused(f"the PLC must be in RUN, but its state is {state}")

    def _check_interface(self) -> None:
        expected_types = self._interface.tag_types()
        found = self._link.tag_types(list(expected_types))
        differences = [
            _type_difference(name, kind, found.get(name))
            for name, kind in expected_types.items()
            if found.get(name) != kind
        ]
        differences += self._start_value_differences(found)
        if differences:
            listed = "; ".join(differences)
            raise PlcRefused(f"the interface in the PLC differs from this warehouse: {listed}")

    def _start_value_differences(self, types: Mapping[str, str | None]) -> list[str]:
        expected = {
            INTERFACE_VERSION_TAG: INTERFACE_VERSION,
            SIGNAL_LIST_VERSION_TAG: SIGNAL_LIST_VERSION,
            CRANE_COUNT_TAG: self._interface.crane_count,
        }
        readable = {name: want for name, want in expected.items() if types.get(name) == "DInt"}
        values = self._link.read(list(readable))
        return [
            f"{name} is {value}, not {want}"
            for (name, want), value in zip(readable.items(), values, strict=True)
            if value != want
        ]

    def _check_heartbeat(self) -> None:
        started = self._clock()
        first = self._link.read([HEARTBEAT_TAG])[0]
        while self._clock() - started < HEARTBEAT_LIMIT_S:
            self._wait(POLL_S)
            if self._link.read([HEARTBEAT_TAG])[0] != first:
                return
        raise PlcRefused(f"plc_heartbeat did not change within {HEARTBEAT_LIMIT_S:g} s")

    def _reset(self) -> None:
        self._link.write({RESET_REQUEST_TAG: True})
        start = CraneSignals()
        self._written = {tag: getattr(start, name) for _, name, tag in self._model_tags}
        self._link.write(dict(self._written))
        started = self._clock()
        while not self._link.read([RESET_DONE_TAG])[0]:
            if self._clock() - started >= RESET_LIMIT_S:
                raise PlcRefused(f"reset_done did not come within {RESET_LIMIT_S:g} s")
            self._wait(POLL_S)
        self._link.write({RESET_REQUEST_TAG: False})

    def _install_interrupt_handler(self) -> None:
        try:
            self._previous_handler = signal.signal(signal.SIGINT, self._on_interrupt)
            self._handler_installed = True
        except ValueError:  # Not on the main thread, where no Ctrl+C can arrive.
            self._handler_installed = False

    def _on_interrupt(self, number: int, frame: FrameType | None) -> None:
        self._interrupted = True

    # Each cycle.

    def scan(self, signals: Mapping[int, CraneSignals]) -> None:
        if self.state in ("created", "refused"):
            raise RuntimeError(f"a controller in state {self.state} cannot exchange")
        if self.state == "stopped":
            raise ControllerStopped(self._stop_reason, self._stop_message)
        self._cycle += 1
        if self._interrupted:
            self._stop("interrupted", "the run was interrupted")
        started = self._clock()
        if self.state == "prepared":
            self.state = "exchanging"
            self._started_at = self._cycle_start = self._heartbeat_changed_at = started
        try:
            self._write_changes(signals)
            values = self._link.read(self._read_names)
        except LinkError as error:
            self._stop("connection_lost", f"the connection to the PLC was lost: {error}")
        finished = self._clock()
        self.last_exchange_ms = (finished - started) * 1000
        self._slowest_ms = max(self._slowest_ms, self.last_exchange_ms)
        self._exchanges += 1
        for (aisle, name, _), value in zip(self._plc_tags, values, strict=False):
            setattr(signals[aisle], name, value)
        self._check_running(values[-1], finished)
        self._wait_for_deadline()

    def _write_changes(self, signals: Mapping[int, CraneSignals]) -> None:
        changes: dict[str, PlcValue] = {}
        jobs: list[tuple[str, PlcValue]] = []
        for aisle, name, tag in self._model_tags:
            value = getattr(signals[aisle], name)
            if value == self._written[tag]:
                continue
            if name == "job_id":
                jobs.append((tag, value))
            else:
                changes[tag] = value
        if changes:
            self._link.write(changes)
            self._written.update(changes)
        # The library may split a request, so a new job_id must follow its complete job data.
        for tag, value in jobs:
            self._link.write({tag: value})
            self._written[tag] = value

    def _check_running(self, heartbeat: PlcValue, now: float) -> None:
        if heartbeat != self._heartbeat:
            self._heartbeat = heartbeat
            self._heartbeat_changed_at = now
        elif now - self._heartbeat_changed_at >= HEARTBEAT_LIMIT_S:
            self._stop(
                "plc_not_running", f"plc_heartbeat has not changed for {HEARTBEAT_LIMIT_S:g} s"
            )

    def _wait_for_deadline(self) -> None:
        deadline = self._cycle_start + self._cycle_s
        now = self._clock()
        if now > deadline:
            self._overruns += 1
            self._cycle_start = now
        else:
            self._wait(deadline - now)
            self._cycle_start = deadline
        self._ended_at = self._clock()

    def _stop(self, reason: str, message: str) -> NoReturn:
        self.state = "stopped"
        self._stop_reason, self._stop_message = reason, message
        self._ended_at = self._clock()
        raise ControllerStopped(reason, message)

    # After a run.

    def stats(self) -> PlcRunStats:
        return PlcRunStats(
            device=self._device,
            interface_version=INTERFACE_VERSION,
            stop_reason=self._stop_reason,
            stopped_at_cycle=None if self._stop_reason == "finished" else self._cycle,
            cycles=self._exchanges,
            overrun_cycles=self._overruns,
            slowest_exchange_ms=self._slowest_ms,
            simulated_s=max(self._cycle, 0) * self._cycle_s,
            real_s=max(self._ended_at - self._started_at, 0.0),
        )

    def close(self) -> None:
        """End the session. The model clears nothing, and writes nothing more."""
        if self._closed:
            return
        self._closed = True
        if self._handler_installed:
            signal.signal(signal.SIGINT, self._previous_handler)
            self._handler_installed = False
        with contextlib.suppress(LinkError):
            self._link.close()


def _type_difference(name: str, expected: str, found: str | None) -> str:
    return f"{name} is missing" if found is None else f"{name} is {found}, not {expected}"
