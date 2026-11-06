"""The value codec, the identity check, and how the real link is opened."""

import sys
from typing import Any

import pytest

from highbay_sim.plc.link import (
    LinkError,
    LinkUnavailable,
    PlcConnection,
    PlcValue,
    confirm_simulated,
    decode,
    encode,
    open_link,
)

SIMULATED = "1;6ES7 SIM-01500-APLC;S4.1"
NOT_SIMULATED = [
    None,
    "",
    "1;6ES7 511-1AK02-0AB0;V2.9",
    "1;6ES7 512-1CK01-0AB0;V2.9",
    "1;SIM 6ES7 SIM-01500-APLC;S4.1",
    "1;6ES7 511-SIM-01500;V2.9",
    "6ES7 SIM-01500-APLC",
    "1;6ES7 SIM-01500-APLC",
    "1;6ES7 SIM-01500-APLC;S4.1;extra",
    "1;6es7 sim-01500-aplc;S4.1",
    "garbage",
]


@pytest.mark.parametrize(
    ("plc_type", "value", "raw"),
    [
        ("LReal", 1.5, b"\x3f\xf8\x00\x00\x00\x00\x00\x00"),
        ("DInt", -2, b"\xff\xff\xff\xfe"),
        ("Bool", True, b"\x01"),
        ("Bool", False, b"\x00"),
    ],
)
def test_values_pass_unchanged(plc_type: Any, value: PlcValue, raw: bytes) -> None:
    assert encode(plc_type, value) == raw
    assert decode(plc_type, raw) == value
    assert type(decode(plc_type, raw)) is type(value)


def test_the_codec_matches_the_library() -> None:
    values = pytest.importorskip("s7commplus.values")
    typeinfo = pytest.importorskip("s7commplus.typeinfo")
    for plc_type, soft_type, value in (
        ("LReal", typeinfo.Softdatatype.LREAL, 12.34),
        ("DInt", typeinfo.Softdatatype.DINT, -70000),
        ("Bool", typeinfo.Softdatatype.BOOL, True),
    ):
        assert encode(plc_type, value) == values.encode(soft_type, value)
        assert decode(plc_type, values.encode(soft_type, value)) == value


@pytest.mark.parametrize(
    ("plc_type", "value"),
    [
        ("LReal", True),
        ("LReal", "1.5"),
        ("DInt", 1.5),
        ("DInt", True),
        ("DInt", 2**31),
        ("Bool", 1),
        ("Bool", 0.0),
    ],
)
def test_a_value_of_the_wrong_type_raises_a_link_error(plc_type: Any, value: Any) -> None:
    with pytest.raises(LinkError):
        encode(plc_type, value)


@pytest.mark.parametrize(
    ("plc_type", "raw"), [("LReal", b"\x00"), ("DInt", b"\x00"), ("Bool", b"\x00\x00")]
)
def test_bytes_of_the_wrong_length_raise_a_link_error(plc_type: Any, raw: bytes) -> None:
    with pytest.raises(LinkError):
        decode(plc_type, raw)


def test_the_documented_simulated_device_is_accepted() -> None:
    assert confirm_simulated(SIMULATED)


@pytest.mark.parametrize("device", NOT_SIMULATED)
def test_anything_else_is_refused(device: str | None) -> None:
    assert not confirm_simulated(device)


def test_the_text_form_of_a_connection_never_shows_the_password() -> None:
    connection = PlcConnection("plc.example", None, "s3cret-value")
    assert "s3cret-value" not in repr(connection)
    assert "s3cret-value" not in str(connection)


@pytest.mark.parametrize("missing", ["highbay_sim.plc.s7_link", "s7commplus"])
def test_a_missing_extra_says_how_to_install_it(
    monkeypatch: pytest.MonkeyPatch, missing: str
) -> None:
    monkeypatch.delitem(sys.modules, "highbay_sim.plc.s7_link", raising=False)
    monkeypatch.setitem(sys.modules, missing, None)
    with pytest.raises(LinkUnavailable, match="uv sync --extra plc"):
        open_link(PlcConnection("plc.example"))
