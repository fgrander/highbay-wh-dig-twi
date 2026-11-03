"""Crane motion for the Omniverse replay, with values worked out by hand."""

import math

import pytest

from highbay.replay.core.motion import axis_distance, movement_position

SPEED = 2.0
ACCELERATION = 1.0


def test_no_distance_or_no_time_means_no_travel() -> None:
    assert axis_distance(0.0, SPEED, ACCELERATION, 5.0) == 0.0
    assert axis_distance(10.0, SPEED, ACCELERATION, 0.0) == 0.0
    assert axis_distance(10.0, SPEED, ACCELERATION, -1.0) == 0.0


def test_long_move_accelerates_cruises_and_brakes() -> None:
    # 10 m at 2 m/s and 1 m/s2: 2 s up (2 m), 3 s at speed (6 m), 2 s down (2 m), 7 s in total.
    assert axis_distance(10.0, SPEED, ACCELERATION, 1.0) == pytest.approx(0.5)  # 1 * 1^2 / 2
    assert axis_distance(10.0, SPEED, ACCELERATION, 2.0) == pytest.approx(2.0)
    assert axis_distance(10.0, SPEED, ACCELERATION, 3.0) == pytest.approx(4.0)  # 2 + 2 * 1
    assert axis_distance(10.0, SPEED, ACCELERATION, 6.0) == pytest.approx(9.5)  # 10 - 1^2 / 2
    assert axis_distance(10.0, SPEED, ACCELERATION, 7.0) == 10.0
    assert axis_distance(10.0, SPEED, ACCELERATION, 100.0) == 10.0


def test_short_move_never_reaches_full_speed() -> None:
    # 1 m at 1 m/s2 is shorter than 2^2 / 1 = 4 m: 2 * sqrt(1 / 1) = 2 s in total.
    assert axis_distance(1.0, SPEED, ACCELERATION, 0.5) == pytest.approx(0.125)  # 0.5^2 / 2
    assert axis_distance(1.0, SPEED, ACCELERATION, 1.0) == pytest.approx(0.5)
    assert axis_distance(1.0, SPEED, ACCELERATION, 1.5) == pytest.approx(0.875)  # 1 - 0.5^2 / 2
    assert axis_distance(1.0, SPEED, ACCELERATION, 2.0) == 1.0


def test_exact_boundary_between_long_and_short_move() -> None:
    # 4 m takes 2 s up and 2 s down, with no time at constant speed.
    assert axis_distance(4.0, SPEED, ACCELERATION, 2.0) == pytest.approx(2.0)
    assert axis_distance(4.0, SPEED, ACCELERATION, 4.0) == 4.0


CRANE = {
    "horizontal": {"speed_m_s": SPEED, "acceleration_m_s2": ACCELERATION},
    "vertical": {"speed_m_s": 1.0, "acceleration_m_s2": 1.0},
}


def test_each_axis_follows_its_own_profile_and_holds_its_target() -> None:
    movement = {"start_s": 10.0, "start_position": [10.0, 0.0], "target_position": [0.0, 1.0]}
    # After 2 s: horizontal travelled 2 m towards 0, and vertical (1 m, 2 s in total) has arrived.
    assert movement_position(movement, CRANE, 12.0) == pytest.approx([8.0, 1.0])
    # After 1 s: horizontal 0.5 m, and vertical 0.5 m.
    assert movement_position(movement, CRANE, 11.0) == pytest.approx([9.5, 0.5])
    assert movement_position(movement, CRANE, 1000.0) == [0.0, 1.0]


def test_position_before_a_movement_starts_is_its_start() -> None:
    movement = {"start_s": 10.0, "start_position": [3.0, 2.0], "target_position": [5.0, 2.0]}
    assert movement_position(movement, CRANE, 9.0) == [3.0, 2.0]


def test_no_rounding_past_the_target() -> None:
    movement = {
        "start_s": 0.0,
        "start_position": [0.1, 0.0],
        "target_position": [0.3, 0.0],
    }
    total = 2 * math.sqrt(0.2 / ACCELERATION)
    assert movement_position(movement, CRANE, total)[0] == 0.3
