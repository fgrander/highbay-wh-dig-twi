"""Crane motion, with values worked out by hand from the formulas in data-model.md."""

import math
from typing import Any

import pytest

from conftest import Modules

CRANE = {
    "horizontal": {"speed_m_s": 2.0, "acceleration_m_s2": 1.0},
    "vertical": {"speed_m_s": 1.0, "acceleration_m_s2": 1.0},
}


@pytest.mark.parametrize(
    ("elapsed", "expected"),
    [
        # d=10, v=2, a=1: accelerating for 2 s, at full speed until d/v = 5 s, braking until 7 s.
        (0.0, 0.0),
        (1.0, 0.5),  # a·t²/2
        (2.0, 2.0),  # v²/(2a)
        (3.0, 4.0),  # 2 + 2·1
        (5.0, 8.0),  # 2 + 2·3
        (6.0, 9.5),  # 10 - 1·1²/2
        (7.0, 10.0),
        (9.0, 10.0),  # after the axis's own time
        (-1.0, 0.0),  # before the start
    ],
)
def test_distance_with_full_speed(modules: Modules, elapsed: float, expected: float) -> None:
    assert modules.call("motion.js", "axisDistance", 10.0, 2.0, 1.0, elapsed) == pytest.approx(
        expected
    )


def test_distance_without_reaching_full_speed(modules: Modules) -> None:
    # d=2, v=2, a=1: v²/a = 4 > 2, so T = 2·sqrt(2) and the midpoint is at 1 m.
    total = 2.0 * math.sqrt(2.0)
    for elapsed, expected in [
        (0.5, 0.125),  # a·t²/2
        (total / 2.0, 1.0),
        (total - 0.5, 2.0 - 0.125),  # d - a·(T-t)²/2
        (total, 2.0),
        (total + 1.0, 2.0),
    ]:
        assert modules.call("motion.js", "axisDistance", 2.0, 2.0, 1.0, elapsed) == pytest.approx(
            expected
        )


def test_zero_distance_stays_at_zero(modules: Modules) -> None:
    assert modules.call("motion.js", "axisDistance", 0.0, 2.0, 1.0, 1.0) == 0.0


def movement(start: list[float], target: list[float]) -> dict[str, Any]:
    return {"start_s": 10.0, "end_s": 17.0, "start_position": start, "target_position": target}


@pytest.mark.parametrize(
    ("time_s", "expected"),
    [
        (10.0, [0.0, 0.0]),
        (11.0, [0.5, 0.5]),
        (12.0, [2.0, 1.5]),
        (13.0, [4.0, 2.5]),
        (14.0, [6.0, 3.0]),  # the vertical axis has finished and holds its target
        (15.0, [8.0, 3.0]),
        (16.0, [9.5, 3.0]),
        (17.0, [10.0, 3.0]),
        (20.0, [10.0, 3.0]),
    ],
)
def test_crane_position_on_both_axes(
    modules: Modules, time_s: float, expected: list[float]
) -> None:
    position = modules.call(
        "motion.js",
        "movementPosition",
        movement([0.0, 0.0], [10.0, 3.0]),
        CRANE,
        time_s,
    )
    assert position == pytest.approx(expected)


def test_crane_position_moving_back(modules: Modules) -> None:
    position = modules.call(
        "motion.js",
        "movementPosition",
        movement([10.0, 3.0], [0.0, 0.0]),
        CRANE,
        12.0,
    )
    assert position == pytest.approx([8.0, 1.5])


def test_movement_of_zero_length(modules: Modules) -> None:
    position = modules.call(
        "motion.js",
        "movementPosition",
        {"start_s": 5.0, "end_s": 5.0, "start_position": [4.0, 3.0], "target_position": [4.0, 3.0]},
        CRANE,
        5.0,
    )
    assert position == [4.0, 3.0]
