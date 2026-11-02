"""FR-011: the simulation and the replay's logic do not depend on Kit or on each other."""

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).parents[2]
CORE = ROOT / "omniverse" / "exts" / "highbay.replay" / "highbay" / "replay" / "core"
SIMULATION = ROOT / "src" / "highbay_sim"


def imported_roots(path: Path) -> set[str]:
    """Returns the top-level names of absolute imports in a file. Relative imports stay inside."""
    roots = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_core_only_uses_the_standard_library() -> None:
    files = sorted(CORE.glob("*.py"))
    assert files
    for path in files:
        outside = imported_roots(path) - set(sys.stdlib_module_names)
        assert not outside, f"{path.name} imports {sorted(outside)}"


def test_simulation_does_not_import_the_replay() -> None:
    files = sorted(SIMULATION.rglob("*.py"))
    assert files
    for path in files:
        assert "highbay" not in imported_roots(path), path.name
