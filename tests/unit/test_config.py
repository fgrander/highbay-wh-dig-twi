import copy
import hashlib
from pathlib import Path
from typing import Any

import pytest
import yaml

from conftest import minimal_scenario_dict, minimal_warehouse_dict, write_yaml
from highbay_sim.config import (
    InputError,
    InputProblem,
    load_inputs,
    load_scenario,
    load_warehouse,
)


def warehouse_problems(tmp_path: Path, content: dict[str, Any]) -> list[InputProblem]:
    with pytest.raises(InputError) as caught:
        load_warehouse(write_yaml(tmp_path / "warehouse.yaml", content))
    return caught.value.problems


def scenario_problems(tmp_path: Path, content: dict[str, Any]) -> list[InputProblem]:
    with pytest.raises(InputError) as caught:
        load_scenario(write_yaml(tmp_path / "scenario.yaml", content))
    return caught.value.problems


def paths(problems: list[InputProblem]) -> set[str]:
    return {problem.field_path for problem in problems}


def changed(base: dict[str, Any], dotted_path: str, value: Any) -> dict[str, Any]:
    content = copy.deepcopy(base)
    *parents, last = dotted_path.split(".")
    target = content
    for key in parents:
        target = target[key]
    target[last] = value
    return content


def test_valid_inputs_load(tmp_path: Path) -> None:
    warehouse = load_warehouse(write_yaml(tmp_path / "w.yaml", minimal_warehouse_dict()))
    scenario = load_scenario(write_yaml(tmp_path / "s.yaml", minimal_scenario_dict()))
    assert warehouse.model.layout.aisle_count == 1
    assert scenario.model.seed == 1


def test_racks_per_aisle_defaults_to_two(tmp_path: Path) -> None:
    content = minimal_warehouse_dict()
    del content["layout"]["racks_per_aisle"]
    warehouse = load_warehouse(write_yaml(tmp_path / "w.yaml", content))
    assert warehouse.model.layout.racks_per_aisle == 2
    assert warehouse.model.layout.cell_count == 20


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", 2),
        ("name", ""),
        ("layout.aisle_count", 0),
        ("layout.aisle_count", 1.5),
        ("layout.racks_per_aisle", 3),
        ("layout.bays_per_rack", 0),
        ("layout.levels_per_rack", -1),
        ("layout.cell.height_m", 0),
        ("layout.cell.length_m", -1.0),
        ("layout.cell.width_m", 0),
        ("crane.horizontal.speed_m_s", 0),
        ("crane.horizontal.acceleration_m_s2", -1),
        ("crane.vertical.speed_m_s", 0),
        ("crane.vertical.acceleration_m_s2", 0),
        ("crane.pick_time_s", -1),
        ("crane.set_time_s", -0.5),
        ("storage_rule", "closest"),
    ],
)
def test_invalid_warehouse_field_is_reported_at_its_path(
    tmp_path: Path, field: str, value: Any
) -> None:
    content = changed(minimal_warehouse_dict(), field, value)
    assert field in paths(warehouse_problems(tmp_path, content))


def test_zero_handling_time_is_valid(tmp_path: Path) -> None:
    content = changed(minimal_warehouse_dict(), "crane.pick_time_s", 0)
    load_warehouse(write_yaml(tmp_path / "w.yaml", content))


def test_unknown_field_is_rejected(tmp_path: Path) -> None:
    content = changed(minimal_warehouse_dict(), "crane.max_speed", 5)
    assert "crane.max_speed" in paths(warehouse_problems(tmp_path, content))


def test_default_without_outbound_point_is_rejected(tmp_path: Path) -> None:
    content = changed(
        minimal_warehouse_dict(), "transfer_points.default", {"left": ["inbound"], "right": []}
    )
    problems = warehouse_problems(tmp_path, content)
    assert "transfer_points.default" in paths(problems)
    assert any("outbound" in problem.message for problem in problems)


def test_override_without_inbound_point_is_rejected(tmp_path: Path) -> None:
    content = changed(minimal_warehouse_dict(), "layout.aisle_count", 2)
    content["transfer_points"]["aisles"] = {2: {"right": ["outbound"]}}
    problems = warehouse_problems(tmp_path, content)
    assert "transfer_points.aisles.2" in paths(problems)
    assert any("inbound" in problem.message for problem in problems)


def test_override_replaces_default_for_its_aisle(tmp_path: Path) -> None:
    content = minimal_warehouse_dict()
    content["transfer_points"]["default"] = {"left": [], "right": []}
    content["transfer_points"]["aisles"] = {1: {"left": ["inbound", "outbound"]}}
    warehouse = load_warehouse(write_yaml(tmp_path / "w.yaml", content))
    assert warehouse.model.ends_with_role(1, "inbound") == ["left"]
    assert warehouse.model.ends_with_role(1, "outbound") == ["left"]


def test_role_listed_twice_at_one_end_is_rejected(tmp_path: Path) -> None:
    content = changed(
        minimal_warehouse_dict(),
        "transfer_points.default",
        {"left": ["inbound", "inbound"], "right": ["outbound"]},
    )
    assert "transfer_points.default.left" in paths(warehouse_problems(tmp_path, content))


def test_override_for_missing_aisle_is_rejected(tmp_path: Path) -> None:
    content = minimal_warehouse_dict()
    content["transfer_points"]["aisles"] = {9: {"left": ["inbound"], "right": ["outbound"]}}
    assert "transfer_points.aisles.9" in paths(warehouse_problems(tmp_path, content))


def test_stock_at_missing_location_is_rejected(tmp_path: Path) -> None:
    content = minimal_warehouse_dict()
    content["initial_stock"] = [
        {"location": {"aisle": 1, "rack": 1, "bay": 6, "level": 1}, "article": "A"}
    ]
    assert "initial_stock.0.location" in paths(warehouse_problems(tmp_path, content))


def test_duplicate_stock_location_is_rejected(tmp_path: Path) -> None:
    entry = {"location": {"aisle": 1, "rack": 1, "bay": 1, "level": 1}, "article": "A"}
    content = minimal_warehouse_dict()
    content["initial_stock"] = [entry, entry]
    assert "initial_stock.1.location" in paths(warehouse_problems(tmp_path, content))


def test_all_warehouse_problems_are_reported_together(tmp_path: Path) -> None:
    entry = {"location": {"aisle": 1, "rack": 1, "bay": 1, "level": 1}, "article": "A"}
    content = changed(minimal_warehouse_dict(), "layout.bays_per_rack", 0)
    content["crane"]["pick_time_s"] = -1
    content["initial_stock"] = [entry, entry]
    content["transfer_points"]["default"] = {"left": ["inbound"]}
    assert {
        "layout.bays_per_rack",
        "crane.pick_time_s",
        "initial_stock.1.location",
        "transfer_points.default",
    } <= paths(warehouse_problems(tmp_path, content))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", ""),
        ("seed", -1),
        ("seed", 1.5),
        ("duration_s", 0),
        ("warmup_s", -1),
        ("warmup_s", 3600),
        ("warmup_s", 7200),
    ],
)
def test_invalid_scenario_field_is_reported_at_its_path(
    tmp_path: Path, field: str, value: Any
) -> None:
    content = changed(minimal_scenario_dict(), field, value)
    assert field in paths(scenario_problems(tmp_path, content))


def generated_scenario() -> dict[str, Any]:
    content = minimal_scenario_dict()
    del content["orders"]
    content["generated"] = {
        "orders_per_hour": 60,
        "storage_share": 0.5,
        "article_weights": {"A": 1},
    }
    return content


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("generated.orders_per_hour", -1),
        ("generated.storage_share", 1.5),
        ("generated.storage_share", -0.1),
        ("generated.article_weights", {"A": 0}),
        ("generated.article_weights", {}),
    ],
)
def test_invalid_generation_parameter_is_rejected(tmp_path: Path, field: str, value: Any) -> None:
    content = changed(generated_scenario(), field, value)
    assert field in paths(scenario_problems(tmp_path, content))


def test_negative_article_weight_is_rejected(tmp_path: Path) -> None:
    content = changed(generated_scenario(), "generated.article_weights", {"A": 1, "B": -1})
    assert "generated.article_weights.B" in paths(scenario_problems(tmp_path, content))


def test_scenario_needs_exactly_one_order_definition(tmp_path: Path) -> None:
    both = generated_scenario()
    both["orders"] = []
    assert "orders" in paths(scenario_problems(tmp_path, both))
    neither = generated_scenario()
    del neither["generated"]
    assert "orders" in paths(scenario_problems(tmp_path, neither))


@pytest.mark.parametrize("time_s", [-1, 3600, 9000])
def test_order_time_outside_duration_is_rejected(tmp_path: Path, time_s: float) -> None:
    content = minimal_scenario_dict()
    content["orders"] = [{"time_s": time_s, "type": "storage", "article": "A"}]
    assert "orders.0.time_s" in paths(scenario_problems(tmp_path, content))


def test_order_type_is_restricted(tmp_path: Path) -> None:
    content = minimal_scenario_dict()
    content["orders"] = [{"time_s": 0, "type": "move", "article": "A"}]
    assert "orders.0.type" in paths(scenario_problems(tmp_path, content))


def test_empty_order_list_is_valid(tmp_path: Path) -> None:
    load_scenario(write_yaml(tmp_path / "s.yaml", minimal_scenario_dict()))


def test_load_inputs_reports_problems_from_both_files(tmp_path: Path) -> None:
    warehouse = write_yaml(
        tmp_path / "w.yaml", changed(minimal_warehouse_dict(), "layout.aisle_count", 0)
    )
    scenario = write_yaml(tmp_path / "s.yaml", changed(minimal_scenario_dict(), "seed", -1))
    with pytest.raises(InputError) as caught:
        load_inputs(warehouse, scenario)
    assert paths(caught.value.problems) == {"layout.aisle_count", "seed"}


def test_problem_format_matches_cli_contract(tmp_path: Path) -> None:
    path = write_yaml(
        tmp_path / "warehouse.yaml", changed(minimal_warehouse_dict(), "layout.aisle_count", 0)
    )
    with pytest.raises(InputError) as caught:
        load_warehouse(path)
    assert str(caught.value.problems[0]).startswith(f"{path}: layout.aisle_count: ")


def test_invalid_yaml_and_missing_file_are_input_problems(tmp_path: Path) -> None:
    broken = tmp_path / "broken.yaml"
    broken.write_text("a: [1, 2", encoding="utf-8")
    with pytest.raises(InputError):
        load_warehouse(broken)
    with pytest.raises(InputError):
        load_warehouse(tmp_path / "missing.yaml")


def test_non_mapping_document_is_an_input_problem(tmp_path: Path) -> None:
    path = tmp_path / "list.yaml"
    path.write_text("- 1\n- 2\n", encoding="utf-8")
    with pytest.raises(InputError):
        load_warehouse(path)


def test_hash_ignores_line_endings_and_key_order(tmp_path: Path) -> None:
    content = minimal_warehouse_dict()
    text = yaml.safe_dump(content, sort_keys=False)
    lf = tmp_path / "lf.yaml"
    lf.write_bytes(text.encode())
    crlf = tmp_path / "crlf.yaml"
    crlf.write_bytes(text.replace("\n", "\r\n").encode())
    reordered = tmp_path / "reordered.yaml"
    reordered.write_text(yaml.safe_dump(content, sort_keys=True), encoding="utf-8")

    reference = load_warehouse(lf).sha256
    assert load_warehouse(crlf).sha256 == reference
    assert load_warehouse(reordered).sha256 == reference
    assert reference != hashlib.sha256(lf.read_bytes()).hexdigest()


def test_hash_changes_with_any_value(tmp_path: Path) -> None:
    base = load_warehouse(write_yaml(tmp_path / "a.yaml", minimal_warehouse_dict())).sha256
    other = changed(minimal_warehouse_dict(), "crane.set_time_s", 11.0)
    assert load_warehouse(write_yaml(tmp_path / "b.yaml", other)).sha256 != base
