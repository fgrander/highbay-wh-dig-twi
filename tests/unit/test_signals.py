"""The signal list in the contract and the code must say the same."""

import re
from dataclasses import fields
from pathlib import Path

from highbay_sim.signals import SIGNAL_LIST_VERSION, SIGNALS, CraneSignals, FaultCode

CONTRACT = (
    Path(__file__).parents[2] / "specs" / "003-time-stepped-plant-model" / "contracts"
) / "signal-list.md"
DIRECTIONS = {
    "From order handling to the controller": "order_handling_to_controller",
    "From the controller to order handling": "controller_to_order_handling",
    "From the controller to the plant": "controller_to_plant",
    "From the plant to the controller": "plant_to_controller",
}


def contract_signals() -> dict[str, tuple[str, str, str]]:
    signals = {}
    direction = None
    for line in CONTRACT.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            direction = DIRECTIONS.get(line[3:])
        elif direction and (row := re.match(r"\| `(\w+)` \| ([^|]+) \|([^|]*)\|", line)):
            signals[row[1]] = (direction, row[2].strip(), row[3].strip())
    return signals


def test_version_is_recorded_in_the_contract() -> None:
    assert SIGNAL_LIST_VERSION == 1
    assert f"**Signal list version**: {SIGNAL_LIST_VERSION}" in CONTRACT.read_text(encoding="utf-8")


def test_definitions_equal_the_contract_in_both_directions() -> None:
    code = {signal.name: (signal.direction, signal.type, signal.unit) for signal in SIGNALS}
    assert code == contract_signals()


def test_every_signal_exists_on_a_crane_and_nothing_else_does() -> None:
    assert {field.name for field in fields(CraneSignals)} == {signal.name for signal in SIGNALS}


def test_fault_codes_equal_the_contract() -> None:
    text = CONTRACT.read_text(encoding="utf-8")
    rows = re.findall(r"^\| (\d+) \| `(\w+)` \|", text, flags=re.MULTILINE)
    assert {(int(code), name) for code, name in rows} == {
        (int(fault), fault.name.lower()) for fault in FaultCode
    }


def test_initial_values_are_zero_or_false() -> None:
    signals = CraneSignals()
    assert all(not getattr(signals, field.name) for field in fields(CraneSignals))


def test_signals_accept_no_undefined_name() -> None:
    signals = CraneSignals()
    try:
        signals.not_a_signal = 1  # type: ignore[attr-defined]
    except AttributeError:
        return
    raise AssertionError("a misspelled signal must not be accepted silently")
