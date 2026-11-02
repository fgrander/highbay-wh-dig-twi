// Crane position at a time, using the same symmetric trapezoidal profile as the simulation.

/** Returns the distance travelled on one axis after `elapsed` seconds, starting at rest. */
export function axisDistance(distance, speed, acceleration, elapsed) {
  if (distance <= 0 || elapsed <= 0) {
    return 0;
  }
  if (distance >= (speed * speed) / acceleration) {
    const total = distance / speed + speed / acceleration;
    const rampTime = speed / acceleration;
    if (elapsed >= total) {
      return distance;
    }
    if (elapsed < rampTime) {
      return (acceleration * elapsed * elapsed) / 2;
    }
    if (elapsed < distance / speed) {
      return (speed * speed) / (2 * acceleration) + speed * (elapsed - rampTime);
    }
    const remaining = total - elapsed;
    return distance - (acceleration * remaining * remaining) / 2;
  }
  const total = 2 * Math.sqrt(distance / acceleration);
  if (elapsed >= total) {
    return distance;
  }
  if (elapsed < total / 2) {
    return (acceleration * elapsed * elapsed) / 2;
  }
  const remaining = total - elapsed;
  return distance - (acceleration * remaining * remaining) / 2;
}

function axisPosition(start, target, axis, elapsed) {
  const distance = Math.abs(target - start);
  const travelled = axisDistance(distance, axis.speed_m_s, axis.acceleration_m_s2, elapsed);
  return travelled >= distance ? target : start + Math.sign(target - start) * travelled;
}

/**
 * Returns [horizontal, vertical] for a movement at a simulated time. Each axis follows its own
 * profile from the start of the movement, and holds its target once it has arrived.
 */
export function movementPosition(movement, crane, time) {
  const elapsed = time - movement.start_s;
  const [startHorizontal, startVertical] = movement.start_position;
  const [targetHorizontal, targetVertical] = movement.target_position;
  return [
    axisPosition(startHorizontal, targetHorizontal, crane.horizontal, elapsed),
    axisPosition(startVertical, targetVertical, crane.vertical, elapsed),
  ];
}
