"""Compares the result files of two runs, with no dependency on the simulation."""

import json
from pathlib import Path
from typing import Any

RESULT_FILE = "result.json"
NOT_AVAILABLE = "not available"


class ComparisonError(Exception):
    pass


def load_result(path: Path) -> dict[str, Any]:
    """Read a result file, or the result file in a directory."""
    file = path / RESULT_FILE if path.is_dir() else path
    try:
        result = json.loads(file.read_text(encoding="utf-8"))
        result["run"], result["metrics"]
    except OSError as error:
        raise ComparisonError(f"cannot read {file}: {error}") from error
    except (ValueError, TypeError, KeyError) as error:
        raise ComparisonError(f"{file} is not a result file: {error}") from error
    return result  # type: ignore[no-any-return]


def compare_results(first: dict[str, Any], second: dict[str, Any]) -> str:
    """Return a table of every metric of two runs of the same inputs, with their deviation."""
    for part in ("warehouse", "scenario"):
        if first["run"][part]["sha256"] != second["run"][part]["sha256"]:
            raise ComparisonError(
                f"the runs used different {part} files, so they cannot be compared"
            )
    lines = [
        f"A: {_execution(first)}",
        f"B: {_execution(second)}",
        "",
        "| Metric | A | B | B - A | Relative |",
        "|---|---|---|---|---|",
    ]
    values = _flattened(second["metrics"])
    for name, value in _flattened(first["metrics"]).items():
        lines.append(_row(name, value, values.get(name)))
    return "\n".join(lines)


def _execution(result: dict[str, Any]) -> str:
    execution = result["run"].get("execution")
    return "event-based" if execution is None else f"time-stepped, {execution['cycle_ms']} ms"


def _flattened(metrics: dict[str, Any], prefix: str = "") -> dict[str, float | None]:
    values: dict[str, float | None] = {}
    for name, value in metrics.items():
        if isinstance(value, dict):
            values.update(_flattened(value, f"{prefix}{name}."))
        else:
            values[f"{prefix}{name}"] = value
    return values


def _row(name: str, first: float | None, second: float | None) -> str:
    if first is None or second is None:
        shown = [_shown(first), _shown(second), NOT_AVAILABLE, NOT_AVAILABLE]
        return f"| {name} | {' | '.join(shown)} |"
    deviation = second - first
    relative = "" if first == 0 else f"{deviation / abs(first):+.2%}"
    return f"| {name} | {first} | {second} | {round(deviation, 6):+} | {relative} |"


def _shown(value: float | None) -> str:
    return NOT_AVAILABLE if value is None else str(value)
