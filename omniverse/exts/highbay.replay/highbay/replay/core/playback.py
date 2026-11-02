"""The simulated clock. Wall-clock time only decides how fast simulated time advances."""

import time
from collections.abc import Callable
from typing import Protocol

SPEEDS = (1, 10, 60, 600, 3600)
INITIAL_SPEED = 60


class TimeSource(Protocol):
    @property
    def range_is_final(self) -> bool: ...

    def time_range(self) -> tuple[float, float]: ...


class Playback:
    def __init__(self, source: TimeSource, clock: Callable[[], float] = time.monotonic) -> None:
        self._source = source
        self._clock = clock
        self._time = source.time_range()[0]
        self._playing = False
        self._speed = INITIAL_SPEED
        self._last_update = clock()

    @property
    def time_s(self) -> float:
        return self._time

    @property
    def playing(self) -> bool:
        return self._playing

    @property
    def speed(self) -> int:
        return self._speed

    def _at_final_end(self) -> bool:
        return self._source.range_is_final and self._time >= self._source.time_range()[1]

    def update(self) -> None:
        now = self._clock()
        if self._playing:
            self.move_to(self._time + (now - self._last_update) * self._speed)
            if self._at_final_end():
                self._playing = False
        self._last_update = now

    def play(self) -> None:
        if self._at_final_end():
            self._time = self._source.time_range()[0]
        self._last_update = self._clock()
        self._playing = True

    def pause(self) -> None:
        self._playing = False

    def restart(self) -> None:
        self._time = self._source.time_range()[0]
        self._playing = False

    def move_to(self, target_s: float) -> None:
        start_s, end_s = self._source.time_range()
        self._time = min(max(target_s, start_s), end_s)

    def set_speed(self, speed: int) -> None:
        if speed not in SPEEDS:
            raise ValueError(f"Unsupported speed: {speed}")
        self._speed = speed
