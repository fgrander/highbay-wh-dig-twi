"""The simulated clock for the Omniverse replay."""

import pytest

from highbay.replay.core.playback import SPEEDS, Playback


class Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


class Source:
    """The parts of a state source that the clock needs."""

    def __init__(self, end_s: float = 100.0, range_is_final: bool = True) -> None:
        self.end_s = end_s
        self.range_is_final = range_is_final

    def time_range(self) -> tuple[float, float]:
        return (0.0, self.end_s)


def playback(source: Source | None = None) -> tuple[Playback, Clock]:
    clock = Clock()
    return Playback(source or Source(), clock=clock), clock


def test_speeds_and_initial_state() -> None:
    assert SPEEDS == (1, 10, 60, 600, 3600)
    player, _ = playback()
    assert player.speed == 60
    assert player.time_s == 0.0
    assert not player.playing


def test_time_only_advances_while_playing_at_its_speed() -> None:
    player, clock = playback()
    clock.now += 5.0
    player.update()
    assert player.time_s == 0.0

    player.set_speed(10)
    player.play()
    clock.now += 2.0
    player.update()
    assert player.time_s == pytest.approx(20.0)

    player.pause()
    clock.now += 2.0
    player.update()
    assert player.time_s == pytest.approx(20.0)


def test_pausing_does_not_count_as_elapsed_time_after_playing_again() -> None:
    player, clock = playback()
    player.set_speed(1)
    clock.now += 50.0
    player.play()
    clock.now += 1.0
    player.update()
    assert player.time_s == pytest.approx(1.0)


def test_unsupported_speed_is_refused() -> None:
    player, _ = playback()
    with pytest.raises(ValueError, match="7"):
        player.set_speed(7)


def test_moving_stays_within_the_range() -> None:
    player, _ = playback()
    player.move_to(-5.0)
    assert player.time_s == 0.0
    player.move_to(500.0)
    assert player.time_s == 100.0
    player.move_to(40.0)
    assert player.time_s == 40.0


def test_final_range_stops_at_its_end_and_plays_again_from_the_start() -> None:
    player, clock = playback()
    player.set_speed(3600)
    player.play()
    clock.now += 1.0
    player.update()
    assert player.time_s == 100.0
    assert not player.playing

    player.play()
    assert player.time_s == 0.0
    assert player.playing


def test_growing_range_holds_at_its_end_and_continues_when_it_grows() -> None:
    source = Source(end_s=10.0, range_is_final=False)
    player, clock = playback(source)
    player.set_speed(10)
    player.play()
    clock.now += 5.0
    player.update()
    assert player.time_s == 10.0
    assert player.playing

    source.end_s = 12.0
    clock.now += 0.1
    player.update()
    assert player.time_s == pytest.approx(11.0)
    assert player.playing


def test_playing_at_the_end_of_a_growing_range_does_not_go_back() -> None:
    source = Source(end_s=10.0, range_is_final=False)
    player, _ = playback(source)
    player.move_to(10.0)
    player.play()
    assert player.time_s == 10.0


def test_restart_goes_to_the_start_and_pauses() -> None:
    player, _ = playback()
    player.move_to(40.0)
    player.play()
    player.restart()
    assert player.time_s == 0.0
    assert not player.playing
