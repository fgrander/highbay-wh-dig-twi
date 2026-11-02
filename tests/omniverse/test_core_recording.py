"""Loading and checking a recording. A file that fails a check is never used, even in part."""

import json
from pathlib import Path
from typing import Any

import pytest

from highbay.replay.core.recording import SUPPORTED_FORMAT_VERSION, load_recording
from highbay.replay.core.state_source import StateSourceError


def valid() -> dict[str, Any]:
    return {
        "format_version": 1,
        "run": {},
        "warehouse": {},
        "articles": [],
        "initial_stock": [],
        "orders": [],
        "events": [],
        "reported": {},
    }


def write(folder: Path, content: Any) -> Path:
    (folder / "replay.json").write_text(json.dumps(content), encoding="utf-8")
    return folder


def test_good_recording_loads(tmp_path: Path) -> None:
    assert SUPPORTED_FORMAT_VERSION == 1
    assert load_recording(write(tmp_path, valid()))["format_version"] == 1


def test_missing_file_names_the_file(tmp_path: Path) -> None:
    with pytest.raises(StateSourceError, match=r"replay\.json") as error:
        load_recording(tmp_path)
    assert str(tmp_path) in str(error.value)
    assert "no recording" in str(error.value)


def test_invalid_json_names_the_file(tmp_path: Path) -> None:
    (tmp_path / "replay.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(StateSourceError, match=r"replay\.json.*damaged"):
        load_recording(tmp_path)


def test_invalid_text_encoding_names_the_file(tmp_path: Path) -> None:
    (tmp_path / "replay.json").write_bytes(b"\xff\xfe\x00")
    with pytest.raises(StateSourceError, match=r"replay\.json.*damaged"):
        load_recording(tmp_path)


def test_other_content_than_a_recording(tmp_path: Path) -> None:
    with pytest.raises(StateSourceError, match="does not contain a recording"):
        load_recording(write(tmp_path, [1, 2]))


def test_unsupported_version_names_both_versions(tmp_path: Path) -> None:
    with pytest.raises(StateSourceError, match=r"format version 999.*version 1"):
        load_recording(write(tmp_path, {**valid(), "format_version": 999}))


@pytest.mark.parametrize(
    "part", ["articles", "initial_stock", "orders", "events", "run", "warehouse", "reported"]
)
def test_missing_part_is_named(tmp_path: Path, part: str) -> None:
    content = valid()
    del content[part]
    with pytest.raises(StateSourceError, match=f'"{part}"'):
        load_recording(write(tmp_path, content))


@pytest.mark.parametrize(
    ("part", "value"),
    [("articles", {}), ("events", "x"), ("run", []), ("warehouse", 1), ("reported", None)],
)
def test_wrong_structure_is_named(tmp_path: Path, part: str, value: Any) -> None:
    with pytest.raises(StateSourceError, match=f'"{part}"'):
        load_recording(write(tmp_path, {**valid(), part: value}))
