"""Crane position at a time, using the same symmetric trapezoidal profile as the simulation."""

import math
from collections.abc import Mapping
from typing import Any


def axis_distance(distance: float, speed: float, acceleration: float, elapsed: float) -> float:
    """Returns the distance travelled on one axis after `elapsed` seconds, starting at rest."""
    if distance <= 0 or elapsed <= 0:
        return 0.0
    if distance >= speed * speed / acceleration:
        total = distance / speed + speed / acceleration
        ramp_time = speed / acceleration
        if elapsed >= total:
            return distance
        if elapsed < ramp_time:
            return acceleration * elapsed * elapsed / 2
        if elapsed < distance / speed:
            return speed * speed / (2 * acceleration) + speed * (elapsed - ramp_time)
        remaining = total - elapsed
        return distance - acceleration * remaining * remaining / 2
    total = 2 * math.sqrt(distance / acceleration)
    if elapsed >= total:
        return distance
    if elapsed < total / 2:
        return acceleration * elapsed * elapsed / 2
    remaining = total - elapsed
    return distance - acceleration * remaining * remaining / 2


def _axis_position(start: float, target: float, axis: Mapping[str, float], elapsed: float) -> float:
    distance = abs(target - start)
    travelled = axis_distance(distance, axis["speed_m_s"], axis["acceleration_m_s2"], elapsed)
    if travelled >= distance:
        return target
    return start + math.copysign(travelled, target - start)


def movement_position(
    movement: Mapping[str, Any], crane: Mapping[str, Any], time_s: float
) -> list[float]:
    """Returns [horizontal, vertical]. Each axis has its own profile, and holds its target."""
    elapsed = time_s - movement["start_s"]
    start_horizontal, start_vertical = movement["start_position"]
    target_horizontal, target_vertical = movement["target_position"]
    return [
        _axis_position(start_horizontal, target_horizontal, crane["horizontal"], elapsed),
        _axis_position(start_vertical, target_vertical, crane["vertical"], elapsed),
    ]
