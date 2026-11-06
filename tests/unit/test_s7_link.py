"""The adapter around the connection library, with a stub in place of its client."""

from types import SimpleNamespace
from typing import Any

import pytest

pytest.importorskip("s7commplus")

from s7commplus.typeinfo import Softdatatype

from highbay_sim.plc.link import LinkError, PlcConnection
from highbay_sim.plc.s7_link import S7Link

PASSWORD = "s3cret-value"
HOST = "plc.example"


class StubClient:
    def __init__(self) -> None:
        self.connect_arguments: dict[str, Any] = {}
        self.connect_error: Exception | None = None
        self.calls: list[str] = []
        self.written: list[dict[str, bytes]] = []
        self.tags = {
            "t.real": Softdatatype.LREAL,
            "t.dint": Softdatatype.DINT,
            "t.bool": Softdatatype.BOOL,
            "t.other": Softdatatype.INT,
        }
        self.values = {"t.real": b"\x3f\xf8" + bytes(6), "t.dint": b"\0\0\0\x07", "t.bool": b"\1"}
        self.failed: dict[str, Exception] = {}
        self.request_error: Exception | None = None
        self.state: Any = "RUN"
        self.disconnected = False
        self._connection: Any = SimpleNamespace(_server_session_version=b"raw")

    def connect(self, host: str, **arguments: Any) -> None:
        self.connect_arguments = {"host": host, **arguments}
        if self.connect_error is not None:
            raise self.connect_error

    def resolve_tag(self, name: str) -> Any:
        if name not in self.tags:
            raise KeyError(name)
        return SimpleNamespace(name=name, softdatatype=self.tags[name])

    def read_tags(self, names: list[str]) -> list[Any]:
        self.calls.append("read")
        if self.request_error is not None:
            raise self.request_error
        return [
            SimpleNamespace(
                tag=self.resolve_tag(name),
                value=self.values.get(name),
                error=self.failed.get(name),
            )
            for name in names
        ]

    def write_tags(self, values: dict[str, bytes]) -> list[Any]:
        self.calls.append("write")
        if self.request_error is not None:
            raise self.request_error
        self.written.append(dict(values))
        return [
            SimpleNamespace(tag=self.resolve_tag(name), value=None, error=self.failed.get(name))
            for name in values
        ]

    def get_cpu_state(self) -> Any:
        if isinstance(self.state, Exception):
            raise self.state
        return self.state

    def disconnect(self) -> None:
        self.disconnected = True


def opened(client: StubClient, connection: PlcConnection | None = None) -> S7Link:
    return S7Link.open(connection or PlcConnection(HOST), client_factory=lambda: client)


def test_without_a_certificate_tls_is_used_if_offered() -> None:
    client = StubClient()
    opened(client)
    assert client.connect_arguments["host"] == HOST
    assert client.connect_arguments["use_tls"] == "auto"
    assert client.connect_arguments["tls_ca"] is None
    assert client.connect_arguments["password"] is None


def test_with_a_certificate_tls_is_required() -> None:
    client = StubClient()
    opened(client, PlcConnection(HOST, "ca.pem", PASSWORD))
    assert client.connect_arguments["use_tls"] is True
    assert client.connect_arguments["tls_ca"] == "ca.pem"
    assert client.connect_arguments["password"] == PASSWORD


def test_device_string_comes_from_the_session(monkeypatch: pytest.MonkeyPatch) -> None:
    client = StubClient()
    monkeypatch.setattr(
        "highbay_sim.plc.s7_link.extract_session_version_string",
        lambda raw: "1;6ES7 SIM-01500-APLC;S4.1" if raw == b"raw" else None,
    )
    assert opened(client).device_string() == "1;6ES7 SIM-01500-APLC;S4.1"


@pytest.mark.parametrize(
    "connection",
    [
        None,
        SimpleNamespace(),
        SimpleNamespace(_server_session_version=None),
        SimpleNamespace(_server_session_version=b"no device string here"),
    ],
)
def test_an_unknown_identity_gives_nothing(connection: Any) -> None:
    client = StubClient()
    client._connection = connection
    assert opened(client).device_string() is None


def test_a_failing_identity_gives_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(raw: bytes) -> str:
        raise ValueError(raw)

    monkeypatch.setattr("highbay_sim.plc.s7_link.extract_session_version_string", broken)
    assert opened(StubClient()).device_string() is None


def test_cpu_state_is_passed_on() -> None:
    client = StubClient()
    assert opened(client).cpu_state() == "RUN"
    client.state = "STOP"
    assert opened(client).cpu_state() == "STOP"


def test_a_failing_cpu_state_is_unknown() -> None:
    client = StubClient()
    client.state = OSError("no answer")
    assert opened(client).cpu_state() == "UNKNOWN"


def test_tag_types_name_each_type_and_nothing_for_a_missing_name() -> None:
    link = opened(StubClient())
    names = ["t.real", "t.dint", "t.bool", "t.other", "t.missing"]
    assert link.tag_types(names) == {
        "t.real": "LReal",
        "t.dint": "DInt",
        "t.bool": "Bool",
        "t.other": "INT",
        "t.missing": None,
    }


def test_read_decodes_by_type_in_order() -> None:
    link = opened(StubClient())
    assert link.read(["t.bool", "t.real", "t.dint"]) == [True, 1.5, 7]


def test_read_raises_on_any_failed_item() -> None:
    client = StubClient()
    client.failed["t.dint"] = OSError("item failed")
    with pytest.raises(LinkError, match=r"t.dint"):
        opened(client).read(["t.real", "t.dint"])


def test_read_raises_a_link_error_when_the_request_fails() -> None:
    client = StubClient()
    client.request_error = OSError("gone")
    with pytest.raises(LinkError, match="gone"):
        opened(client).read(["t.real"])


def test_write_keeps_the_order_in_one_call() -> None:
    client = StubClient()
    opened(client).write({"t.dint": 7, "t.bool": True, "t.real": 1.5})
    assert client.calls == ["write"]
    assert list(client.written[0]) == ["t.dint", "t.bool", "t.real"]
    assert client.written[0]["t.dint"] == b"\0\0\0\x07"


def test_write_raises_on_any_failed_item_and_does_not_retry() -> None:
    client = StubClient()
    client.failed["t.bool"] = OSError("item failed")
    with pytest.raises(LinkError, match=r"t.bool"):
        opened(client).write({"t.real": 1.5, "t.bool": True})
    assert client.calls == ["write"]


def test_a_failed_write_request_is_not_retried() -> None:
    client = StubClient()
    client.request_error = OSError("gone")
    with pytest.raises(LinkError):
        opened(client).write({"t.real": 1.5})
    assert client.calls == ["write"]


def test_writing_a_tag_of_an_unknown_name_sends_nothing() -> None:
    client = StubClient()
    with pytest.raises(LinkError, match=r"t.missing"):
        opened(client).write({"t.missing": 1})
    assert client.calls == []


def test_writing_a_tag_of_an_unsupported_type_sends_nothing() -> None:
    client = StubClient()
    with pytest.raises(LinkError, match=r"t.other"):
        opened(client).write({"t.other": 1})
    assert client.calls == []


def test_a_connection_failure_holds_neither_host_nor_password() -> None:
    client = StubClient()
    client.connect_error = OSError(f"cannot reach {HOST} with {PASSWORD}")
    with pytest.raises(LinkError) as failed:
        opened(client, PlcConnection(HOST, None, PASSWORD))
    assert PASSWORD not in str(failed.value)
    assert HOST not in str(failed.value)
    assert failed.value.__cause__ is None


def test_a_request_failure_holds_neither_host_nor_password() -> None:
    client = StubClient()
    link = opened(client, PlcConnection(HOST, None, PASSWORD))
    client.request_error = OSError(f"lost {HOST} with {PASSWORD}")
    with pytest.raises(LinkError) as failed:
        link.read(["t.real"])
    assert PASSWORD not in str(failed.value)
    assert HOST not in str(failed.value)


def test_a_refused_login_without_a_password_says_what_is_missing() -> None:
    client = StubClient()
    client.connect_error = OSError("Legitimation failed: the PLC needs a password")
    with pytest.raises(LinkError, match="HIGHBAY_PLC_PASSWORD"):
        opened(client)


def test_a_failed_certificate_check_says_what_is_missing() -> None:
    client = StubClient()
    client.connect_error = OSError("certificate verify failed")
    with pytest.raises(LinkError, match="--plc-tls-ca"):
        opened(client)


def test_close_ends_the_session() -> None:
    client = StubClient()
    opened(client).close()
    assert client.disconnected


def test_a_failing_close_raises_nothing() -> None:
    client = StubClient()

    def broken() -> None:
        raise OSError("gone")

    client.disconnect = broken  # type: ignore[method-assign]
    opened(client).close()
