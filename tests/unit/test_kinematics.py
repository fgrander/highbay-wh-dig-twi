import math

import pytest

from highbay_sim.kinematics import axis_position, axis_travel_time, movement_time


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


# Long profile: 10 m at 2 m/s and 1 m/s². Ramps take 2 s and cover 2 m each, and the total is 7 s.
@pytest.mark.parametrize(
    ("elapsed_s", "expected_m"),
    [
        (-1.0, 0.0),
        (0.0, 0.0),
        (1.0, 0.5),  # a·t²/2
        (2.0, 2.0),  # end of acceleration
        (3.0, 4.0),  # 2 m + 2 m/s · 1 s
        (5.0, 8.0),  # start of braking: 10 m - 2 m
        (6.0, 9.5),  # 10 m - a·(7 - 6)²/2
        (7.0, 10.0),
        (9.0, 10.0),
    ],
)
def test_axis_position_on_a_long_profile(elapsed_s: float, expected_m: float) -> None:
    assert axis_position(0.0, 10.0, 2.0, 1.0, elapsed_s) == pytest.approx(expected_m)


# Short profile: 2 m at 2 m/s and 1 m/s² peaks at sqrt(2) s, at 1 m, and the total is 2·sqrt(2) s.
@pytest.mark.parametrize(
    ("elapsed_s", "expected_m"),
    [
        (1.0, 0.5),
        (math.sqrt(2.0), 1.0),
        (2.0, 2.0 - (2.0 * math.sqrt(2.0) - 2.0) ** 2 / 2.0),
        (2.0 * math.sqrt(2.0), 2.0),
    ],
)
def test_axis_position_on_a_short_profile(elapsed_s: float, expected_m: float) -> None:
    assert axis_position(0.0, 2.0, 2.0, 1.0, elapsed_s) == pytest.approx(expected_m)


def test_axis_position_moving_backward_from_any_start() -> None:
    assert axis_position(14.0, 4.0, 2.0, 1.0, 1.0) == pytest.approx(13.5)
    assert axis_position(14.0, 4.0, 2.0, 1.0, 7.0) == 4.0


def test_axis_position_with_zero_distance_stays_at_start() -> None:
    assert axis_position(3.0, 3.0, 2.0, 1.0, 5.0) == 3.0


def test_axis_position_is_exactly_the_target_at_the_travel_time() -> None:
    distance = 7.3
    end_s = axis_travel_time(distance, 3.0, 0.5)
    assert axis_position(1.1, 1.1 + distance, 3.0, 0.5, end_s) == 1.1 + distance
