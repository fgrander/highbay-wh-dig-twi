"""The only way the rest of the project reaches a PLC. This file does not import the library."""

import importlib
import math
import struct
from dataclasses import dataclass, field
from typing import Literal, Protocol, cast

PlcType = Literal["LReal", "DInt", "Bool"]
PlcValue = float | int | bool

_SIMULATED_ORDER_NUMBER = "6ES7 SIM-"
_DEVICE_STRING_PARTS = 3
_DINT_MIN, _DINT_MAX = -(2**31), 2**31 - 1
_FORMATS: dict[PlcType, str] = {"LReal": ">d", "DInt": ">i", "Bool": ">?"}


class LinkError(Exception):
    """A request to the PLC failed. Writes are never retried."""


class LinkUnavailable(LinkError):
    """The connection library cannot be used."""


@dataclass(frozen=True)
class PlcConnection:
    """Where the PLC is, given from outside the repository. Its text form hides the password."""

    host: str
    tls_ca: str | None = None
    password: str | None = field(default=None, repr=False)


class TagLink(Protocol):
    def device_string(self) -> str | None:
        """The device string of the session, or None if it is unknown."""
        ...

    def cpu_state(self) -> str:
        """RUN, STOP, or UNKNOWN."""
        ...

    def tag_types(self, names: list[str]) -> dict[str, str | None]:
        """The PLC type of each name, or None for a missing name."""
        ...

    def read(self, names: list[str]) -> list[PlcValue]:
        """The values, in order. Raises LinkError on any failed item."""
        ...

    def write(self, values: dict[str, PlcValue]) -> None:
        """Write in the given order. Raises LinkError on any failed item, and never retries."""
        ...

    def close(self) -> None: ...


def confirm_simulated(device_string: str | None) -> bool:
    """Whether a device string names a simulated PLC. Anything unclear counts as not simulated."""
    if not device_string:
        return False
    parts = device_string.split(";")
    return len(parts) == _DEVICE_STRING_PARTS and parts[1].startswith(_SIMULATED_ORDER_NUMBER)


def encode(plc_type: PlcType, value: object) -> bytes:
    if not _fits(plc_type, value):
        raise LinkError(f"{value!r} is not a value of type {plc_type}")
    return struct.pack(_FORMATS[plc_type], cast(PlcValue, value))


def decode(plc_type: PlcType, raw: bytes) -> PlcValue:
    try:
        return cast(PlcValue, struct.unpack(_FORMATS[plc_type], raw)[0])
    except struct.error as error:
        raise LinkError(f"{len(raw)} bytes are not a value of type {plc_type}") from error


def _fits(plc_type: PlcType, value: object) -> bool:
    if plc_type == "Bool":
        return isinstance(value, bool)
    if isinstance(value, bool):
        return False
    if plc_type == "DInt":
        return isinstance(value, int) and _DINT_MIN <= value <= _DINT_MAX
    return isinstance(value, int | float) and not (isinstance(value, float) and math.isnan(value))


def open_link(connection: PlcConnection) -> TagLink:
    """Connect to a PLC. The library is imported here, and only when a PLC is asked for."""
    try:
        module = importlib.import_module("highbay_sim.plc.s7_link")
    except ImportError as error:
        raise LinkUnavailable(
            "the PLC connection is not installed, run: uv sync --extra plc"
        ) from error
    return cast(TagLink, module.S7Link.open(connection))
