"""Controllers read and write signals in each cycle, and know nothing else about the plant."""

import hashlib
import importlib.util
from collections.abc import Mapping
from enum import Enum, auto
from pathlib import Path
from typing import Protocol, cast

from highbay_sim.signals import CraneSignals

POSITION_TOLERANCE_M = 0.001


class Controller(Protocol):
    def scan(self, signals: Mapping[int, CraneSignals]) -> None:
        """Read the signals of each crane and write commands, once per cycle."""
        ...


class ControllerLoadError(Exception):
    pass


class ControllerStopped(Exception):
    """A controller ends a run early, and what was recorded so far is kept."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message


def load_controller(specification: str) -> tuple[Controller, str, str]:
    """Load `FILE.py:CLASS`, and return the controller, its name, and the file's SHA-256."""
    file_text, separator, class_name = specification.rpartition(":")
    if not separator or not class_name.isidentifier():
        raise ControllerLoadError(f"controller {specification!r} is not in the form FILE.py:CLASS")
    path = Path(file_text)
    try:
        content = path.read_bytes()
        module_spec = importlib.util.spec_from_file_location("highbay_user_controller", path)
        if module_spec is None or module_spec.loader is None:
            raise ControllerLoadError(f"controller file {path} is not a Python file")
        module = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(module)
        controller = getattr(module, class_name)()
    except ControllerLoadError:
        raise
    except Exception as error:
        raise ControllerLoadError(
            f"controller {specification!r} cannot be loaded: {error}"
        ) from error
    if not callable(getattr(controller, "scan", None)):
        raise ControllerLoadError(f"controller {specification!r} has no scan method")
    name = f"{path.name}:{class_name}"
    return cast(Controller, controller), name, hashlib.sha256(content).hexdigest()


class _State(Enum):
    IDLE = auto()
    TO_SOURCE = auto()
    PICKING = auto()
    TO_DESTINATION = auto()
    SETTING = auto()


class BuiltInController:
    """Carries out one transport job per crane: to the source, pick, to the destination, set."""

    def __init__(self) -> None:
        self._states: dict[int, _State] = {}

    def scan(self, signals: Mapping[int, CraneSignals]) -> None:
        for aisle, crane in signals.items():
            crane.horizontal_start = crane.vertical_start = False
            crane.pick_start = crane.set_start = False
            if crane.fault_code:
                continue
            self._states[aisle] = self._next_state(self._states.get(aisle, _State.IDLE), crane)

    def _next_state(self, state: _State, crane: CraneSignals) -> _State:
        if state is _State.IDLE:
            return self._go_to_source(crane) if crane.job_id != crane.job_done_id else state
        if state is _State.TO_SOURCE:
            return self._pick(crane) if _in_position(crane) else state
        if state is _State.PICKING:
            return self._go_to_destination(crane) if crane.load_present else state
        if state is _State.TO_DESTINATION:
            return self._set(crane) if _in_position(crane) else state
        if crane.load_present:
            return state
        crane.job_done_id = crane.job_id
        return _State.IDLE

    def _go_to_source(self, crane: CraneSignals) -> _State:
        if _is_at(crane, crane.source_horizontal_m, crane.source_vertical_m):
            return self._pick(crane)
        _start_movement(crane, crane.source_horizontal_m, crane.source_vertical_m)
        return _State.TO_SOURCE

    def _pick(self, crane: CraneSignals) -> _State:
        crane.side = crane.source_side
        crane.pick_start = True
        return _State.PICKING

    def _go_to_destination(self, crane: CraneSignals) -> _State:
        if _is_at(crane, crane.destination_horizontal_m, crane.destination_vertical_m):
            return self._set(crane)
        _start_movement(crane, crane.destination_horizontal_m, crane.destination_vertical_m)
        return _State.TO_DESTINATION

    def _set(self, crane: CraneSignals) -> _State:
        crane.side = crane.destination_side
        crane.set_start = True
        return _State.SETTING


def _in_position(crane: CraneSignals) -> bool:
    return crane.horizontal_in_position and crane.vertical_in_position


def _is_at(crane: CraneSignals, horizontal_m: float, vertical_m: float) -> bool:
    return (
        abs(crane.horizontal_actual_m - horizontal_m) <= POSITION_TOLERANCE_M
        and abs(crane.vertical_actual_m - vertical_m) <= POSITION_TOLERANCE_M
    )


def _start_movement(crane: CraneSignals, horizontal_m: float, vertical_m: float) -> None:
    crane.horizontal_target_m = horizontal_m
    crane.vertical_target_m = vertical_m
    crane.horizontal_start = crane.vertical_start = True
