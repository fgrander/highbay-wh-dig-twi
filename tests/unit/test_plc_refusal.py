"""SC-003: a device that is not confirmed as simulated receives no write."""

import ast
from pathlib import Path

import pytest
from test_plc_link import NOT_SIMULATED

from data.memory_plc import MemoryPlc
from highbay_sim.cli import _parser
from highbay_sim.plc.controller import PlcController, PlcRefused
from highbay_sim.plc.interface import PlcInterface

SOURCE = Path(__file__).parents[2] / "src"
ONLY_IMPORTER = SOURCE / "highbay_sim" / "plc" / "s7_link.py"
ONLY_WRITER = SOURCE / "highbay_sim" / "plc" / "controller.py"


@pytest.mark.parametrize("device", NOT_SIMULATED)
def test_a_device_that_is_not_confirmed_receives_no_write(device: str | None) -> None:
    plc = MemoryPlc(PlcInterface(1), device=device)
    controller = PlcController(plc, plc.interface, 50, clock=plc.now, wait=plc.wait)
    with pytest.raises(PlcRefused) as refused:
        controller.prepare()
    assert plc.write_requests == []
    assert plc.requests == 0
    assert plc.closed
    assert controller.state == "refused"
    if device:
        assert device in str(refused.value)


def test_a_device_that_fails_to_identify_itself_receives_no_write() -> None:
    plc = MemoryPlc(PlcInterface(1))
    plc.identity_error = OSError("no identity")
    controller = PlcController(plc, plc.interface, 50, clock=plc.now, wait=plc.wait)
    with pytest.raises(PlcRefused, match="no identity"):
        controller.prepare()
    assert plc.write_requests == []
    assert plc.closed


def test_a_refused_device_cannot_be_written_to_afterwards() -> None:
    plc = MemoryPlc(PlcInterface(1), device=None)
    controller = PlcController(plc, plc.interface, 50, clock=plc.now, wait=plc.wait)
    with pytest.raises(PlcRefused):
        controller.prepare()
    with pytest.raises(RuntimeError):
        controller.prepare()
    with pytest.raises(RuntimeError):
        controller.scan({})
    assert plc.write_requests == []


def test_no_option_turns_the_check_off() -> None:
    parser = _parser()
    commands = next(
        action for action in parser._actions if hasattr(action, "choices") and action.choices
    )
    for name in ("run", "plc-measure"):
        command = commands.choices[name]  # type: ignore[index]
        options = {option for action in command._actions for option in action.option_strings}
        plc_options = {option for option in options if "plc" in option}
        assert plc_options == {"--plc-host", "--plc-tls-ca"}
        assert not {o for o in options if any(w in o for w in ("force", "skip", "unsafe"))}


def python_files() -> list[Path]:
    return sorted(SOURCE.rglob("*.py"))


def imports_library(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(
            alias.name.split(".")[0] == "s7commplus" for alias in node.names
        ):
            return True
        if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "s7commplus":
            return True
    return False


def writes_to_a_link(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "write"
            and isinstance(node.func.value, ast.Attribute | ast.Name)
            and "link" in ast.unparse(node.func.value)
        ):
            return True
    return False


def test_only_the_adapter_imports_the_library() -> None:
    assert [path for path in python_files() if imports_library(path)] == [ONLY_IMPORTER]


def test_only_the_controller_writes_to_a_link() -> None:
    assert [path for path in python_files() if writes_to_a_link(path)] == [ONLY_WRITER]
