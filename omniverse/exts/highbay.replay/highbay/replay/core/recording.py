"""Loads and checks a recording. A file that fails a check is never used, even in part."""

import json
from pathlib import Path
from typing import Any

from .state_source import StateSourceError

RECORDING_FILE = "replay.json"
SUPPORTED_FORMAT_VERSION = 1

_PARTS = (
    ("articles", list),
    ("initial_stock", list),
    ("orders", list),
    ("events", list),
    ("run", dict),
    ("warehouse", dict),
    ("reported", dict),
)


def _problem_in(content: Any) -> str | None:
    if not isinstance(content, dict):
        return "the file does not contain a recording."
    version = content.get("format_version")
    if version != SUPPORTED_FORMAT_VERSION:
        return (
            f"the file has format version {version}, "
            f"but this application supports version {SUPPORTED_FORMAT_VERSION}."
        )
    for part, expected in _PARTS:
        if not isinstance(content.get(part), expected):
            return f'the file is damaged: "{part}" is missing or has the wrong structure.'
    return None


def load_recording(folder: Path | str) -> dict[str, Any]:
    """Returns the checked content of a run folder's recording, or raises StateSourceError."""
    path = Path(folder) / RECORDING_FILE
    try:
        content = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise StateSourceError(f"{path}: no recording found.") from None
    except ValueError as error:  # Includes text that is not valid UTF-8.
        raise StateSourceError(f"{path}: the file is damaged and cannot be read: {error}") from None
    except OSError as error:
        raise StateSourceError(f"{path}: the file could not be read: {error}") from None
    problem = _problem_in(content)
    if problem:
        raise StateSourceError(f"{path}: {problem}")
    return content  # type: ignore[no-any-return]
