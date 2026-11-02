// Finds the selected cell from a ray and the warehouse layout. This costs the same at any warehouse
// size, and also finds empty cells, which have no drawn object.

/** Returns the [entry, exit] distances of a ray through a box, or null if it misses. */
function rayThroughBox(ray, min, max) {
  let entry = 0;
  let exit = Infinity;
  for (let axis = 0; axis < 3; axis += 1) {
    const origin = ray.origin[axis];
    const direction = ray.direction[axis];
    if (direction === 0) {
      if (origin < min[axis] || origin > max[axis]) {
        return null;
      }
    } else {
      const first = (min[axis] - origin) / direction;
      const second = (max[axis] - origin) / direction;
      entry = Math.max(entry, Math.min(first, second));
      exit = Math.min(exit, Math.max(first, second));
    }
  }
  return entry < exit ? [entry, exit] : null;
}

function racksAlongRay(layout, ray) {
  const halfWidth = layout.cell.width_m / 2;
  const racks = [];
  for (let aisle = 1; aisle <= layout.aisleCount; aisle += 1) {
    for (let rack = 1; rack <= layout.racksPerAisle; rack += 1) {
      const z = layout.rackZ(aisle, rack);
      const hit = rayThroughBox(
        ray,
        [0, 0, z - halfWidth],
        [layout.length, layout.height, z + halfWidth],
      );
      if (hit) {
        racks.push({ aisle, rack, entry: hit[0], exit: hit[1] });
      }
    }
  }
  return racks.sort((first, second) => first.entry - second.entry);
}

/** Returns the distances at which a ray crosses from one cell of a rack to the next. */
function crossings(ray, axis, spacing, count, entry, exit) {
  const distances = [];
  if (ray.direction[axis] !== 0) {
    for (let index = 1; index < count; index += 1) {
      const distance = (index * spacing - ray.origin[axis]) / ray.direction[axis];
      if (distance > entry && distance < exit) {
        distances.push(distance);
      }
    }
  }
  return distances;
}

function clampedIndex(position, spacing, count) {
  return Math.min(Math.max(Math.floor(position / spacing) + 1, 1), count);
}

/** Returns the cells of one rack along a ray, nearest first. */
function cellsInRack(layout, ray, { aisle, rack, entry, exit }) {
  const { length_m, height_m } = layout.cell;
  const limits = [
    entry,
    ...crossings(ray, 0, length_m, layout.bays, entry, exit),
    ...crossings(ray, 1, height_m, layout.levels, entry, exit),
    exit,
  ].sort((first, second) => first - second);

  const cells = [];
  for (let index = 0; index + 1 < limits.length; index += 1) {
    const middle = (limits[index] + limits[index + 1]) / 2;
    const x = ray.origin[0] + ray.direction[0] * middle;
    const y = ray.origin[1] + ray.direction[1] * middle;
    cells.push([
      aisle,
      rack,
      clampedIndex(x, length_m, layout.bays),
      clampedIndex(y, height_m, layout.levels),
    ]);
  }
  return cells;
}

/**
 * Returns the first occupied cell along a ray, seen through any empty cells, or otherwise the
 * nearest cell. Returns null if the ray hits no rack.
 */
export function pickCell(layout, ray, isOccupied = () => false) {
  let nearest = null;
  for (const rack of racksAlongRay(layout, ray)) {
    for (const location of cellsInRack(layout, ray, rack)) {
      nearest = nearest ?? location;
      if (isOccupied(location)) {
        return location;
      }
    }
  }
  return nearest;
}
