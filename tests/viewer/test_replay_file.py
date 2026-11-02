import json
from typing import Any

import pytest

from conftest import Modules


def valid_replay() -> dict[str, Any]:
    return {
        "format_version": 1,
        "run": {"duration_s": 10.0, "window": {"start_s": 0.0, "end_s": 10.0}},
        "warehouse": {
            "layout": {},
            "crane": {},
            "transfer_points": {},
            "crane_start_positions": {},
        },
        "articles": [],
        "initial_stock": [],
        "order_columns": [],
        "orders": [],
        "event_columns": [],
        "events": [],
        "reported": {},
    }


def parse(modules: Modules, text: str) -> dict[str, Any]:
    return modules.call("replay-file.js", "parseReplay", text)


def test_valid_file_loads(modules: Modules) -> None:
    parsed = parse(modules, json.dumps(valid_replay()))
    assert parsed["error"] is None
    assert parsed["data"]["format_version"] == 1


@pytest.mark.parametrize("text", ["", "{damaged", '{"format_version":1,"run":{'])
def test_invalid_json_gives_an_error_and_no_data(modules: Modules, text: str) -> None:
    parsed = parse(modules, text)
    assert parsed["data"] is None
    assert parsed["error"]


@pytest.mark.parametrize("text", ["[]", "1", "null"])
def test_json_that_is_not_an_object_gives_an_error(modules: Modules, text: str) -> None:
    parsed = parse(modules, text)
    assert parsed["data"] is None
    assert parsed["error"]


def test_unsupported_version_names_both_versions(modules: Modules) -> None:
    content = valid_replay()
    content["format_version"] = 999
    parsed = parse(modules, json.dumps(content))
    assert parsed["data"] is None
    assert "999" in parsed["error"]
    assert "1" in parsed["error"].replace("999", "")


@pytest.mark.parametrize(
    "part", ["run", "warehouse", "articles", "initial_stock", "orders", "events", "reported"]
)
def test_missing_part_gives_an_error(modules: Modules, part: str) -> None:
    content = valid_replay()
    del content[part]
    parsed = parse(modules, json.dumps(content))
    assert parsed["data"] is None
    assert part in parsed["error"]


@pytest.mark.parametrize(
    ("part", "value"),
    [("events", {}), ("orders", 1), ("articles", "A"), ("run", []), ("warehouse", [])],
)
def test_part_with_wrong_structure_gives_an_error(modules: Modules, part: str, value: Any) -> None:
    content = valid_replay()
    content[part] = value
    parsed = parse(modules, json.dumps(content))
    assert parsed["data"] is None
    assert part in parsed["error"]


def test_failed_request_gives_an_error(modules: Modules) -> None:
    loaded = modules.call("replay-file.js", "loadReplay", "/missing-file.json")
    assert loaded["data"] is None
    assert loaded["error"]
