"""Writes every change of every signal to signals.csv, as in contracts/results.md."""

import csv
from collections.abc import Mapping
from operator import attrgetter
from pathlib import Path
from types import TracebackType
from typing import Self

from highbay_sim.signals import SIGNALS, CraneSignals

HEADER = ("cycle", "time_s", "crane", "signal", "value")
_NAMES = tuple(signal.name for signal in SIGNALS)
_read_all = attrgetter(*_NAMES)


class SignalRecorder:
    def __init__(self, path: Path, signals: Mapping[int, CraneSignals]) -> None:
        self._signals = signals
        self._file = path.open("w", encoding="utf-8", newline="")
        self._writer = csv.writer(self._file, lineterminator="\n")
        self._writer.writerow(HEADER)
        self._last: dict[int, tuple[object, ...]] = {}

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        kind: type[BaseException] | None,
        value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._file.close()

    def record(self, cycle: int, time_s: float) -> None:
        """Write what has changed since the last cycle, or every signal in the first cycle."""
        for aisle, crane in self._signals.items():
            values = _read_all(crane)
            last = self._last.get(aisle)
            if values == last:
                continue
            for index, value in enumerate(values):
                if last is None or value != last[index]:
                    self._writer.writerow((cycle, time_s, aisle, _NAMES[index], _shown(value)))
            self._last[aisle] = values


def _shown(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return repr(value)
