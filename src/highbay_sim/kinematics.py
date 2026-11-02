"""Crane travel times for a symmetric trapezoidal velocity profile."""

import math


def axis_travel_time(distance_m: float, speed_m_s: float, acceleration_m_s2: float) -> float:
    """Return the time to travel a distance, starting and ending at rest."""
    distance = abs(distance_m)
    if distance >= speed_m_s**2 / acceleration_m_s2:
        return distance / speed_m_s + speed_m_s / acceleration_m_s2
    return 2.0 * math.sqrt(distance / acceleration_m_s2)


def movement_time(
    horizontal_distance_m: float,
    vertical_distance_m: float,
    horizontal_speed_m_s: float,
    horizontal_acceleration_m_s2: float,
    vertical_speed_m_s: float,
    vertical_acceleration_m_s2: float,
) -> float:
    """Return the time of a movement in which both axes travel at the same time."""
    return max(
        axis_travel_time(horizontal_distance_m, horizontal_speed_m_s, horizontal_acceleration_m_s2),
        axis_travel_time(vertical_distance_m, vertical_speed_m_s, vertical_acceleration_m_s2),
    )


def axis_position(
    start_m: float, target_m: float, speed_m_s: float, acceleration_m_s2: float, elapsed_s: float
) -> float:
    """Return where an axis is after a time, starting at rest and stopping exactly at its target."""
    distance = abs(target_m - start_m)
    if elapsed_s <= 0.0:
        return start_m
    total = axis_travel_time(distance, speed_m_s, acceleration_m_s2)
    if elapsed_s >= total:
        return target_m
    remaining = total - elapsed_s
    ramp = min(speed_m_s / acceleration_m_s2, total / 2.0)
    if elapsed_s < ramp:
        travelled = acceleration_m_s2 * elapsed_s * elapsed_s / 2.0
    elif remaining <= ramp:
        travelled = distance - acceleration_m_s2 * remaining * remaining / 2.0
    else:
        travelled = speed_m_s * (elapsed_s - ramp / 2.0)
    return start_m + math.copysign(travelled, target_m - start_m)
