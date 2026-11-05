"""The real adapter against the library's in-memory server, which runs no PLC program.

It shows that the adapter connects, and that an unconfirmed device receives no write. It does not
show that the connection works on a real S7-PLCSIM Advanced instance.
"""

import socket
from collections.abc import Iterator
from typing import Any

import pytest

pytest.importorskip("s7commplus")

from s7commplus import Server

from highbay_sim.plc.controller import PlcController, PlcRefused
from highbay_sim.plc.interface import PlcInterface
from highbay_sim.plc.link import LinkError, PlcConnection
from highbay_sim.plc.s7_link import S7Link


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


@pytest.fixture
def server() -> Iterator[tuple[Any, int]]:
    port = free_port()
    emulator = Server()
    emulator.register_db(1, {"value": ("Real", 0)}, size=16)
    emulator.start(host="127.0.0.1", port=port)
    try:
        yield emulator, port
    finally:
        emulator.stop()


def test_the_emulator_is_connected_to_and_refused_with_nothing_written(
    server: tuple[Any, int],
) -> None:
    emulator, port = server
    before = bytes(emulator.get_db(1).data)
    link = S7Link.open(PlcConnection("127.0.0.1"), port=port)
    controller = PlcController(link, PlcInterface(1), 50)
    with pytest.raises(PlcRefused, match="not confirmed as a simulated PLC"):
        controller.prepare()
    assert bytes(emulator.get_db(1).data) == before
    assert controller.state == "refused"


def test_a_device_that_nothing_listens_on_gives_a_link_error() -> None:
    with pytest.raises(LinkError):
        S7Link.open(PlcConnection("127.0.0.1"), port=free_port())
