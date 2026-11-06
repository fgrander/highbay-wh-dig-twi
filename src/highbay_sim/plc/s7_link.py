"""The real link. This is the only file that imports the connection library, s7commplus.

The library has no public call for the device string, so this reads a private attribute of its
connection. The exact version pin covers that, and any failure there makes the identity unknown, and
so makes the device refused.
"""

from collections.abc import Callable
from typing import Any, Final, cast

from s7commplus import Client
from s7commplus.legitimation import extract_session_version_string

from highbay_sim.plc.link import LinkError, PlcConnection, PlcType, PlcValue, decode, encode

DEFAULT_PORT: Final = 102
_PLC_TYPES: Final[dict[str, PlcType]] = {"LREAL": "LReal", "DINT": "DInt", "BOOL": "Bool"}


class S7Link:
    """A TagLink over an open session."""

    def __init__(self, client: Any, connection: PlcConnection) -> None:
        self._client = client
        self._connection = connection
        self._types: dict[str, PlcType] = {}

    @classmethod
    def open(
        cls,
        connection: PlcConnection,
        port: int = DEFAULT_PORT,
        client_factory: Callable[[], Any] = Client,
    ) -> "S7Link":
        client = client_factory()
        try:
            client.connect(
                connection.host,
                port=port,
                use_tls=True if connection.tls_ca else "auto",
                tls_ca=connection.tls_ca,
                password=connection.password,
            )
        except Exception as error:
            raise LinkError(_connect_problem(error, connection)) from None
        return cls(client, connection)

    def device_string(self) -> str | None:
        try:
            raw: bytes | None = self._client._connection._server_session_version
            return None if raw is None else extract_session_version_string(raw)
        except Exception:
            return None

    def cpu_state(self) -> str:
        try:
            return str(self._client.get_cpu_state())
        except Exception:
            return "UNKNOWN"

    def tag_types(self, names: list[str]) -> dict[str, str | None]:
        return {name: self._tag_type(name) for name in names}

    def _tag_type(self, name: str) -> str | None:
        try:
            soft_type: str = self._client.resolve_tag(name).softdatatype.name
        except KeyError:
            return None
        except Exception as error:
            raise LinkError(self._shown(error)) from None
        return _PLC_TYPES.get(soft_type, soft_type)

    def read(self, names: list[str]) -> list[PlcValue]:
        try:
            results = self._client.read_tags(names)
        except Exception as error:
            raise LinkError(self._shown(error)) from None
        values: list[PlcValue] = []
        for name, result in zip(names, results, strict=True):
            if result.error is not None:
                raise LinkError(f"reading {name} failed: {self._shown(result.error)}") from None
            values.append(decode(self._plc_type(name), result.value))
        return values

    def write(self, values: dict[str, PlcValue]) -> None:
        # Encoding comes first, so that a bad value or a wrong tag sends nothing at all.
        raw = {name: encode(self._plc_type(name), value) for name, value in values.items()}
        try:
            results = self._client.write_tags(raw)
        except Exception as error:
            raise LinkError(self._shown(error)) from None
        for name, result in zip(raw, results, strict=True):
            if result.error is not None:
                raise LinkError(f"writing {name} failed: {self._shown(result.error)}") from None

    def close(self) -> None:
        try:
            self._client.disconnect()
        except Exception:
            # Nothing more is sent after a run, so a failed goodbye changes no result.
            return

    def _plc_type(self, name: str) -> PlcType:
        known = self._types.get(name)
        if known is not None:
            return known
        shown = self._tag_type(name)
        if shown is None:
            raise LinkError(f"the PLC has no tag {name}")
        if shown not in _PLC_TYPES.values():
            raise LinkError(f"tag {name} has the unsupported type {shown}")
        plc_type = cast(PlcType, shown)
        self._types[name] = plc_type
        return plc_type

    def _shown(self, error: BaseException) -> str:
        return _hidden(str(error), self._connection)


def _hidden(text: str, connection: PlcConnection) -> str:
    """Error text with neither the address nor the password in it."""
    if connection.password:
        text = text.replace(connection.password, "***")
    return text.replace(connection.host, "the PLC")


def _connect_problem(error: Exception, connection: PlcConnection) -> str:
    text = _hidden(str(error), connection)
    lowered = text.lower()
    if "certificate" in lowered and not connection.tls_ca:
        return f"the PLC's certificate needs checking, give it with --plc-tls-ca: {text}"
    if ("legitimation" in lowered or "password" in lowered) and not connection.password:
        return f"the PLC needs a password, set HIGHBAY_PLC_PASSWORD: {text}"
    return f"connecting to the PLC failed: {text}"
