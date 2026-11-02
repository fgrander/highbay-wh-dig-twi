"""The built-in controller, with signals set by hand and no plant."""

import ast
from pathlib import Path

from highbay_sim import controller as controller_module
from highbay_sim.controller import BuiltInController
from highbay_sim.signals import CraneSignals


def job(signals: CraneSignals, number: int = 1) -> None:
    signals.job_id = number
    signals.source_horizontal_m, signals.source_vertical_m, signals.source_side = 0.0, 0.0, 0
    signals.destination_horizontal_m = 10.0
    signals.destination_vertical_m = 3.0
    signals.destination_side = 2


def at_rest(signals: CraneSignals, horizontal_m: float, vertical_m: float) -> None:
    signals.horizontal_actual_m, signals.vertical_actual_m = horizontal_m, vertical_m
    signals.horizontal_in_position = signals.vertical_in_position = True


def started(signals: CraneSignals) -> bool:
    return signals.horizontal_start or signals.vertical_start


class Scan:
    def __init__(self) -> None:
        self.signals = CraneSignals()
        self.controller = BuiltInController()
        at_rest(self.signals, 5.0, 0.0)

    def __call__(self) -> None:
        self.controller.scan({1: self.signals})


def test_stays_idle_with_no_job() -> None:
    scan = Scan()
    scan()
    assert not started(scan.signals)
    assert not scan.signals.pick_start
    assert scan.signals.job_done_id == 0


def test_new_job_starts_both_axes_towards_the_source() -> None:
    scan = Scan()
    job(scan.signals)
    scan()
    assert scan.signals.horizontal_start and scan.signals.vertical_start
    assert (scan.signals.horizontal_target_m, scan.signals.vertical_target_m) == (0.0, 0.0)
    assert not scan.signals.pick_start


def test_a_job_starting_at_the_source_picks_at_once() -> None:
    scan = Scan()
    at_rest(scan.signals, 0.0, 0.0)
    job(scan.signals)
    scan()
    assert not started(scan.signals)
    assert scan.signals.pick_start
    assert scan.signals.side == 0


def test_starts_are_held_for_one_cycle_only() -> None:
    scan = Scan()
    job(scan.signals)
    scan()
    scan.signals.horizontal_in_position = scan.signals.vertical_in_position = False
    scan()
    assert not started(scan.signals)


def test_picks_only_once_both_axes_are_in_position() -> None:
    scan = Scan()
    job(scan.signals)
    scan()
    scan.signals.horizontal_in_position = scan.signals.vertical_in_position = False
    scan.signals.vertical_in_position = True
    scan()
    assert not scan.signals.pick_start
    at_rest(scan.signals, 0.0, 0.0)
    scan()
    assert scan.signals.pick_start


def full_job_up_to_the_destination(scan: Scan) -> None:
    at_rest(scan.signals, 0.0, 0.0)
    job(scan.signals)
    scan()  # pick starts
    scan.signals.handling_active = True
    scan()
    assert not scan.signals.pick_start
    scan.signals.handling_active = False
    scan.signals.load_present = True
    scan()  # moves on


def test_after_the_pick_it_moves_to_the_destination() -> None:
    scan = Scan()
    full_job_up_to_the_destination(scan)
    assert scan.signals.horizontal_start and scan.signals.vertical_start
    assert (scan.signals.horizontal_target_m, scan.signals.vertical_target_m) == (10.0, 3.0)


def test_sets_with_the_destination_side_and_then_reports_the_job_done() -> None:
    scan = Scan()
    full_job_up_to_the_destination(scan)
    scan.signals.horizontal_in_position = scan.signals.vertical_in_position = False
    scan()
    at_rest(scan.signals, 10.0, 3.0)
    scan()
    assert scan.signals.set_start
    assert scan.signals.side == 2
    assert scan.signals.job_done_id == 0
    scan.signals.handling_active = True
    scan()
    assert not scan.signals.set_start
    assert scan.signals.job_done_id == 0
    scan.signals.handling_active = False
    scan.signals.load_present = False
    scan()
    assert scan.signals.job_done_id == 1


def test_takes_the_next_job_after_reporting_the_last_one() -> None:
    scan = Scan()
    full_job_up_to_the_destination(scan)
    scan.signals.horizontal_in_position = scan.signals.vertical_in_position = False
    scan()
    at_rest(scan.signals, 10.0, 3.0)
    scan()
    scan.signals.load_present = False
    scan()
    job(scan.signals, 2)
    scan()
    assert scan.signals.horizontal_start


def test_each_crane_is_handled_on_its_own() -> None:
    first, second = CraneSignals(), CraneSignals()
    at_rest(first, 5.0, 0.0)
    at_rest(second, 5.0, 0.0)
    job(first)
    BuiltInController().scan({1: first, 2: second})
    assert first.horizontal_start
    assert not second.horizontal_start


def test_controller_module_depends_only_on_signals() -> None:
    tree = ast.parse(Path(controller_module.__file__).read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert {name for name in imported if name.startswith("highbay_sim")} == {"highbay_sim.signals"}
