"""The simulated clock, with an injected clock instead of real time."""

from typing import Any

import pytest

from conftest import Modules


def run(modules: Modules, script: str, duration_s: float = 1000.0) -> Any:
    return modules.run(
        "const { createPlayback, SPEEDS } = await imports('playback.js');"
        "let now = 0;"
        "const advance = (seconds) => { now += seconds * 1000; playback.update(); };"
        "const playback = createPlayback({ duration_s: args[0], clock: () => now });"
        f"{script}",
        duration_s,
    )


def test_initial_values(modules: Modules) -> None:
    assert run(modules, "return [playback.time_s, playback.playing, playback.speed];") == [
        0.0,
        False,
        60,
    ]


def test_speeds(modules: Modules) -> None:
    assert run(modules, "return SPEEDS;") == [1, 10, 60, 600, 3600]


def test_time_does_not_advance_while_paused(modules: Modules) -> None:
    assert run(modules, "advance(10); return playback.time_s;") == 0.0


def test_simulated_time_is_real_time_multiplied_by_speed(modules: Modules) -> None:
    script = "playback.setSpeed(10); playback.play(); advance(2); return playback.time_s;"
    assert run(modules, script) == pytest.approx(20.0)


def test_changing_speed_keeps_the_current_time(modules: Modules) -> None:
    script = (
        "playback.setSpeed(10); playback.play(); advance(2);"
        "playback.setSpeed(1); const kept = playback.time_s; advance(3);"
        "return [kept, playback.time_s];"
    )
    assert run(modules, script) == pytest.approx([20.0, 23.0])


def test_pause_stops_time_without_a_jump_on_resume(modules: Modules) -> None:
    script = (
        "playback.setSpeed(10); playback.play(); advance(1); playback.pause(); advance(5);"
        "const paused = playback.time_s; playback.play(); advance(1);"
        "return [paused, playback.time_s];"
    )
    assert run(modules, script) == pytest.approx([10.0, 20.0])


def test_stops_at_the_end_of_the_run(modules: Modules) -> None:
    script = (
        "playback.setSpeed(3600); playback.play(); advance(10);"
        "return [playback.time_s, playback.playing];"
    )
    assert run(modules, script) == [1000.0, False]


def test_play_at_the_end_starts_again(modules: Modules) -> None:
    script = (
        "playback.moveTo(1000); playback.play(); const start = playback.time_s;"
        "return [start, playback.playing];"
    )
    assert run(modules, script) == [0.0, True]


def test_restart_goes_to_zero_and_pauses(modules: Modules) -> None:
    script = (
        "playback.play(); advance(1); playback.restart();"
        "return [playback.time_s, playback.playing];"
    )
    assert run(modules, script) == [0.0, False]


@pytest.mark.parametrize(("target", "expected"), [(-5.0, 0.0), (500.0, 500.0), (5000.0, 1000.0)])
def test_moving_stays_within_the_run(modules: Modules, target: float, expected: float) -> None:
    assert run(modules, f"playback.moveTo({target}); return playback.time_s;") == expected


def test_moving_while_playing_continues_from_the_new_time(modules: Modules) -> None:
    script = (
        "playback.setSpeed(1); playback.play(); advance(5); playback.moveTo(100); advance(1);"
        "return playback.time_s;"
    )
    assert run(modules, script) == pytest.approx(101.0)


def test_unknown_speed_is_refused(modules: Modules) -> None:
    assert run(modules, "try { playback.setSpeed(7); } catch { return playback.speed; }") == 60
