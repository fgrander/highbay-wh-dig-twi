// The only module that decides how objects look. To use detailed models, replace these functions:
// each creates the object for one type from dimensions, and the rest of the viewer only places it.

import * as THREE from "three";

// Kept apart from the crane activity colors below, so that the two are not confused.
const ARTICLE_COLORS = [
  "#c9b27c",
  "#5aa89a",
  "#b5587a",
  "#8fae4e",
  "#7d8fb3",
  "#a67c52",
  "#c7c24a",
  "#5f7f5f",
];
const ACTIVITY_COLORS = {
  moving_empty: "#2f6fd6",
  moving_loaded: "#e8842c",
  handling: "#8a4fc7",
  idle: "#8a8f96",
};
const RACK_COLOR = "#7c8794";
const INBOUND_COLOR = "#3fae5a";
const OUTBOUND_COLOR = "#d35454";
const FLOOR_COLOR = "#e4e7ea";
const HIGHLIGHT_COLOR = "#000000";
const LOAD_SIZE_SHARE = 0.85;
const CRANE_THICKNESS_SHARE = 0.5;

export const BACKGROUND_COLOR = "#f4f5f7";

/** Returns the color of an article, from a fixed sequence in `articles` order. */
export function articleColor(index) {
  return ARTICLE_COLORS[index % ARTICLE_COLORS.length];
}

/** Returns the color of a crane doing an activity. */
export function activityColor(activity) {
  return ACTIVITY_COLORS[activity];
}

function pushRackGrid(positions, layout, z) {
  const { length, height, cell, bays, levels } = layout;
  for (let bay = 0; bay <= bays; bay += 1) {
    const x = bay * cell.length_m;
    positions.push(x, 0, z, x, height, z);
  }
  for (let level = 0; level <= levels; level += 1) {
    const y = level * cell.height_m;
    positions.push(0, y, z, length, y, z);
  }
}

/** Creates the frames of all racks as one object. */
export function createRackFrames(layout) {
  const positions = [];
  const halfWidth = layout.cell.width_m / 2;
  for (let aisle = 1; aisle <= layout.aisleCount; aisle += 1) {
    for (let rack = 1; rack <= layout.racksPerAisle; rack += 1) {
      const z = layout.rackZ(aisle, rack);
      pushRackGrid(positions, layout, z - halfWidth);
      pushRackGrid(positions, layout, z + halfWidth);
    }
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  return new THREE.LineSegments(
    geometry,
    new THREE.LineBasicMaterial({ color: RACK_COLOR, transparent: true, opacity: 0.35 }),
  );
}

/** Creates the outline around a selected object, which stays visible through other objects. */
export function createHighlight(layout) {
  const { length_m, height_m, width_m } = layout.cell;
  const outline = new THREE.LineSegments(
    new THREE.EdgesGeometry(new THREE.BoxGeometry(length_m, height_m, width_m)),
    new THREE.LineBasicMaterial({ color: HIGHLIGHT_COLOR, depthTest: false }),
  );
  outline.renderOrder = 1;
  outline.visible = false;
  return outline;
}

/** Creates the instanced load units in cells, with room for one in every cell. */
export function createStoredLoadUnits(layout) {
  const { length_m, height_m, width_m } = layout.cell;
  const geometry = new THREE.BoxGeometry(
    length_m * LOAD_SIZE_SHARE,
    height_m * LOAD_SIZE_SHARE,
    width_m * LOAD_SIZE_SHARE,
  );
  const mesh = new THREE.InstancedMesh(
    geometry,
    new THREE.MeshLambertMaterial({ color: "#ffffff" }),
    layout.cellCount,
  );
  mesh.count = 0;
  mesh.frustumCulled = false;
  return mesh;
}

/** Creates a crane: a mast that moves along the aisle, and a carriage that moves up it. */
export function createCrane(layout) {
  const { length_m, height_m, width_m } = layout.cell;
  const thickness = width_m * CRANE_THICKNESS_SHARE;
  const material = new THREE.MeshLambertMaterial({ color: activityColor("idle") });

  const mast = new THREE.Mesh(
    new THREE.BoxGeometry(length_m * 0.12, layout.height, thickness),
    material,
  );
  mast.position.y = layout.height / 2;

  const carriage = new THREE.Mesh(
    new THREE.BoxGeometry(length_m * 0.9, height_m * 0.1, thickness * 1.3),
    material,
  );
  const carriedLoad = new THREE.Mesh(
    new THREE.BoxGeometry(
      length_m * LOAD_SIZE_SHARE,
      height_m * LOAD_SIZE_SHARE,
      width_m * LOAD_SIZE_SHARE,
    ),
    new THREE.MeshLambertMaterial({ color: "#ffffff" }),
  );
  carriedLoad.position.y = (height_m * LOAD_SIZE_SHARE) / 2 + height_m * 0.05;
  carriedLoad.visible = false;
  carriage.add(carriedLoad);

  const group = new THREE.Group();
  group.add(mast, carriage);
  return { group, mast, carriage, carriedLoad, material };
}

/** Creates a flat marker for a transfer point. */
export function createTransferPoint(layout, role) {
  const { length_m, width_m } = layout.cell;
  const size = Math.min(length_m, width_m) * 0.8;
  const color = role === "inbound" ? INBOUND_COLOR : OUTBOUND_COLOR;
  const marker = new THREE.Mesh(
    new THREE.BoxGeometry(size, size * 0.1, size / 2),
    new THREE.MeshLambertMaterial({ color }),
  );
  marker.position.y = size * 0.05;
  return marker;
}

/** Creates the floor below the warehouse. */
export function createFloor(bounds) {
  const margin = Math.max(bounds.max[0] - bounds.min[0], bounds.max[2] - bounds.min[2]) * 0.05;
  const width = bounds.max[0] - bounds.min[0] + margin * 2;
  const depth = bounds.max[2] - bounds.min[2] + margin * 2;
  const floor = new THREE.Mesh(
    new THREE.PlaneGeometry(width, depth),
    new THREE.MeshLambertMaterial({ color: FLOOR_COLOR }),
  );
  floor.rotation.x = -Math.PI / 2;
  floor.position.set((bounds.min[0] + bounds.max[0]) / 2, 0, (bounds.min[2] + bounds.max[2]) / 2);
  return floor;
}
