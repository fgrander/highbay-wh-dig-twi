"""A test controller written only from the signal list, as a fixed sequence of steps.

It handles aisle 1 only, and it differs on purpose from the built-in state machine: each step is a
pair of a command and the condition that ends it, and a start stays true until the condition holds.
"""

from collections.abc import Callable, Mapping

from highbay_sim.signals import CraneSignals

Step = tuple[Callable[[CraneSignals], None], Callable[[CraneSignals], bool]]


def _in_position(crane: CraneSignals) -> bool:
    return crane.horizontal_in_position and crane.vertical_in_position


def _go_to_source(crane: CraneSignals) -> None:
    crane.horizontal_target_m = crane.source_horizontal_m
    crane.vertical_target_m = crane.source_vertical_m
    crane.horizontal_start = crane.vertical_start = True


def _pick(crane: CraneSignals) -> None:
    crane.horizontal_start = crane.vertical_start = False
    crane.side = crane.source_side
    crane.pick_start = True


def _go_to_destination(crane: CraneSignals) -> None:
    crane.pick_start = False
    crane.horizontal_target_m = crane.destination_horizontal_m
    crane.vertical_target_m = crane.destination_vertical_m
    crane.horizontal_start = crane.vertical_start = True


def _set(crane: CraneSignals) -> None:
    crane.horizontal_start = crane.vertical_start = False
    crane.side = crane.destination_side
    crane.set_start = True


def _finish(crane: CraneSignals) -> None:
    crane.set_start = False
    crane.job_done_id = crane.job_id


_SEQUENCE: tuple[Step, ...] = (
    (_go_to_source, _in_position),
    (_pick, lambda crane: crane.load_present),
    (_go_to_destination, _in_position),
    (_set, lambda crane: not crane.load_present),
    (_finish, lambda crane: True),
)


class ScriptedController:
    def __init__(self) -> None:
        self._step = -1
        self._just_commanded = False

    def scan(self, signals: Mapping[int, CraneSignals]) -> None:
        crane = signals[1]
        if self._step < 0:
            if crane.job_id == crane.job_done_id:
                return
            self._step = 0
            _SEQUENCE[0][0](crane)
            self._just_commanded = True
            return
        if self._just_commanded:
            # A command's result appears in the next cycle's status, so wait one cycle.
            self._just_commanded = False
            return
        if _SEQUENCE[self._step][1](crane):
            self._step += 1
            if self._step == len(_SEQUENCE):
                self._step = -1
                return
            _SEQUENCE[self._step][0](crane)
            self._just_commanded = True
