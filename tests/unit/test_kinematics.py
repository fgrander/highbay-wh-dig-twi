import math

import pytest

from highbay_sim.kinematics import axis_travel_time, movement_time


def test_long_distance_reaches_full_speed() -> None:
    assert axis_travel_time(10.0, 2.0, 1.0) == pytest.approx(7.0)


def test_vertical_example_from_verification_scenario() -> None:
    assert axis_travel_time(3.0, 1.0, 1.0) == pytest.approx(4.0)


def test_short_distance_never_reaches_full_speed() -> None:
    assert axis_travel_time(2.0, 2.0, 1.0) == pytest.approx(2.0 * math.sqrt(2.0))


def test_zero_distance_takes_no_time() -> None:
    assert axis_travel_time(0.0, 2.0, 1.0) == 0.0


def test_both_branches_agree_at_threshold() -> None:
    speed, acceleration = 3.0, 0.5
    threshold = speed**2 / acceleration
    just_below = axis_travel_time(threshold * (1 - 1e-12), speed, acceleration)
    at_threshold = axis_travel_time(threshold, speed, acceleration)
    assert just_below == pytest.approx(at_threshold)


def test_movement_takes_longer_axis_time() -> None:
    assert movement_time(10.0, 3.0, 2.0, 1.0, 1.0, 1.0) == pytest.approx(7.0)
    assert movement_time(2.0, 12.0, 2.0, 1.0, 1.0, 1.0) == pytest.approx(13.0)


def test_movement_uses_distance_regardless_of_direction() -> None:
    assert movement_time(-10.0, -3.0, 2.0, 1.0, 1.0, 1.0) == pytest.approx(7.0)
