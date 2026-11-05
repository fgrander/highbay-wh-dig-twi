"""The PLC interface follows from the signal list and from contracts/plc-interface.md."""

import re
from pathlib import Path

import pytest

from conftest import minimal_warehouse_dict
from highbay_sim.config import WarehouseDefinition
from highbay_sim.plc.interface import INTERFACE_VERSION, PlcInterface, plc_type_of
from highbay_sim.signals import SIGNALS

CONTRACT = (
    Path(__file__).parents[2] / "specs/006-plc-virtual-commissioning/contracts/plc-interface.md"
)
MODEL_DIRECTIONS = {"order_handling_to_controller", "plant_to_controller"}


def signal_of(tag: str) -> str:
    return tag.rsplit(".", 1)[1]


def test_every_signal_belongs_to_exactly_one_writer_by_its_direction() -> None:
    interface = PlcInterface(1)
    model = {signal_of(tag) for tag in interface.model_tags}
    plc = {signal_of(tag) for tag in interface.plc_tags}
    assert model.isdisjoint(plc)
    assert model | plc == {signal.name for signal in SIGNALS}
    assert model == {signal.name for signal in SIGNALS if signal.direction in MODEL_DIRECTIONS}


def test_tag_names_follow_the_signal_list() -> None:
    interface = PlcInterface(2)
    assert "HB_Interface.crane_1.horizontal_actual_m" in interface.model_tags
    assert "HB_Interface.crane_2.job_done_id" in interface.plc_tags
    assert interface.tag(2, "job_id") == "HB_Interface.crane_2.job_id"
    assert len(interface.model_tags) + len(interface.plc_tags) == 2 * len(SIGNALS)


@pytest.mark.parametrize(
    ("signal_type", "plc_type"),
    [
        ("number", "LReal"),
        ("integer", "DInt"),
        ("boolean", "Bool"),
        ("boolean, rising edge", "Bool"),
    ],
)
def test_signal_types_map_to_plc_types(signal_type: str, plc_type: str) -> None:
    signal = next(signal for signal in SIGNALS if signal.type == signal_type)
    assert plc_type_of(signal) == plc_type


def test_all_tags_have_a_type() -> None:
    types = PlcInterface(2).tag_types()
    assert types["HB_Interface.crane_2.job_id"] == "DInt"
    assert types["HB_Interface.crane_1.horizontal_target_m"] == "LReal"
    assert types["HB_Interface.crane_1.pick_start"] == "Bool"
    assert types["HB_Interface.plc_heartbeat"] == "DInt"
    assert len(types) == 2 * len(SIGNALS) + 6


@pytest.mark.parametrize("crane_count", [0, -1])
def test_crane_count_must_be_at_least_1(crane_count: int) -> None:
    with pytest.raises(ValueError, match="at least 1"):
        PlcInterface(crane_count)


def test_crane_count_is_the_number_of_aisles() -> None:
    document = minimal_warehouse_dict()
    document["layout"]["aisle_count"] = 3
    interface = PlcInterface.for_warehouse(WarehouseDefinition.model_validate(document))
    assert interface.crane_count == 3


def test_header_tags_match_the_contract() -> None:
    text = CONTRACT.read_text(encoding="utf-8")
    rows = re.findall(r"^\| `(HB_Interface\.\w+)` \| `(\w+)` \|", text, re.MULTILINE)
    assert dict(rows) == PlcInterface(1).header_tags
    assert len(rows) == 6


def test_contract_states_the_interface_version() -> None:
    text = CONTRACT.read_text(encoding="utf-8")
    assert f"**Interface version**: {INTERFACE_VERSION}," in text
