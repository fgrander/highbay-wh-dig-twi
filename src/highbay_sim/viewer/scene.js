// Builds the 3D scene and updates it from a replay state. How objects look is left to appearance.js.

import * as THREE from "three";
import {
  activityColor,
  articleColor,
  BACKGROUND_COLOR,
  createCrane,
  createFloor,
  createHighlight,
  createRackFrames,
  createStoredLoadUnits,
  createTransferPoint,
} from "./appearance.js";
import { pickCell } from "./picking.js";
import { OrbitControls } from "./vendor/OrbitControls.js";

const TRANSFER_ROLES = ["inbound", "outbound"];
const ENDS = ["left", "right"];
// Steep and nearly along the aisles, so that stored stock does not hide the cranes.
const VIEW_DIRECTION = new THREE.Vector3(0.3, 0.9, 0.15).normalize();
const FIELD_OF_VIEW_DEGREES = 45;

const locationKey = ([aisle, rack, bay, level]) => `${aisle}-${rack}-${bay}-${level}`;

export class WarehouseScene {
  constructor(container, data, layout) {
    this.container = container;
    this.data = data;
    this.layout = layout;
    this.bounds = layout.bounds();

    this.renderer = new THREE.WebGLRenderer({ antialias: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.append(this.renderer.domElement);

    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(BACKGROUND_COLOR);
    this.scene.add(new THREE.AmbientLight("#ffffff", 1.6));
    const sun = new THREE.DirectionalLight("#ffffff", 1.8);
    sun.position.set(0.5, 1, 0.8);
    this.scene.add(sun);

    this.camera = new THREE.PerspectiveCamera(FIELD_OF_VIEW_DEGREES, 1, 0.1, 1000);

    this.scene.add(createFloor(this.bounds), createRackFrames(layout));
    this.storedLoadUnits = createStoredLoadUnits(layout);
    this.scene.add(this.storedLoadUnits);
    this.slotOfCell = new Map();
    this.cellOfSlot = [];
    this.instanceMatrix = new THREE.Matrix4();
    this.instanceColor = new THREE.Color();

    this.transferPointCount = this.addTransferPoints();
    this.cranes = new Map();
    for (let aisle = 1; aisle <= layout.aisleCount; aisle += 1) {
      const crane = createCrane(layout);
      crane.group.position.z = layout.aisleCenterZ(aisle);
      this.scene.add(crane.group);
      this.cranes.set(aisle, crane);
    }

    this.highlight = createHighlight(layout);
    this.scene.add(this.highlight);
    this.raycaster = new THREE.Raycaster();

    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.resize();
    new ResizeObserver(() => this.resize()).observe(container);
    this.showWholeWarehouse();
  }

  get canvas() {
    return this.renderer.domElement;
  }

  addTransferPoints() {
    let count = 0;
    const { layout } = this;
    for (let aisle = 1; aisle <= layout.aisleCount; aisle += 1) {
      const ends = this.data.warehouse.transfer_points[aisle];
      for (const end of ENDS) {
        const roles = TRANSFER_ROLES.filter((role) => ends[end].includes(role));
        roles.forEach((role, index) => {
          const marker = createTransferPoint(layout, role);
          const sideBySide = roles.length === 2 ? (index - 0.5) * 0.5 * layout.aisleWidth : 0;
          marker.position.x = layout.endX(end);
          marker.position.z = layout.aisleCenterZ(aisle) + sideBySide;
          this.scene.add(marker);
          count += 1;
        });
      }
    }
    return count;
  }

  resize() {
    const width = Math.max(this.container.clientWidth, 1);
    const height = Math.max(this.container.clientHeight, 1);
    this.renderer.setSize(width, height);
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
  }

  /** Returns where the camera looks and how far away it must be to see the whole warehouse. */
  wholeWarehouseView() {
    const { min, max } = this.bounds;
    const center = new THREE.Vector3(...min).add(new THREE.Vector3(...max)).multiplyScalar(0.5);
    const radius = new THREE.Vector3(...max).sub(new THREE.Vector3(...min)).length() / 2;
    const verticalHalfAngle = THREE.MathUtils.degToRad(this.camera.fov) / 2;
    const horizontalHalfAngle = Math.atan(Math.tan(verticalHalfAngle) * this.camera.aspect);
    const distance = (radius / Math.sin(Math.min(verticalHalfAngle, horizontalHalfAngle))) * 1.02;
    return { center, distance };
  }

  showWholeWarehouse() {
    const { center, distance } = this.wholeWarehouseView();
    this.camera.position.copy(center).addScaledVector(VIEW_DIRECTION, distance);
    this.camera.near = Math.max(distance / 500, 0.01);
    this.camera.far = distance * 20;
    this.camera.updateProjectionMatrix();
    this.controls.target.copy(center);
    this.controls.update();
    this.camera.updateMatrixWorld();
  }

  craneColor(aisle) {
    return `#${this.cranes.get(aisle).material.color.getHexString()}`;
  }

  cameraPosition() {
    return this.camera.position.toArray();
  }

  /** Returns where a 3D point appears in the browser window, as [x, y]. */
  screenPosition(point) {
    this.camera.updateMatrixWorld();
    const projected = new THREE.Vector3(...point).project(this.camera);
    const box = this.canvas.getBoundingClientRect();
    return [
      box.left + ((projected.x + 1) / 2) * box.width,
      box.top + ((1 - projected.y) / 2) * box.height,
    ];
  }

  craneCarriagePoint(aisle) {
    const { group, carriage } = this.cranes.get(aisle);
    return [group.position.x, carriage.position.y, group.position.z];
  }

  craneScreenPosition(aisle) {
    return this.screenPosition(this.craneCarriagePoint(aisle));
  }

  cellScreenPosition(location) {
    return this.screenPosition(this.layout.cellBox(location).center);
  }

  /** Returns what is at a point in the window: a crane, a cell, or null. Cranes come first. */
  pickAt(clientX, clientY, state) {
    const box = this.canvas.getBoundingClientRect();
    const pointer = new THREE.Vector2(
      ((clientX - box.left) / box.width) * 2 - 1,
      1 - ((clientY - box.top) / box.height) * 2,
    );
    // A click can come before the next frame, so positions set since the last one must count.
    this.scene.updateMatrixWorld();
    this.camera.updateMatrixWorld();
    this.raycaster.setFromCamera(pointer, this.camera);
    for (const [aisle, crane] of this.cranes) {
      if (this.raycaster.intersectObject(crane.group, true).some((hit) => hit.object.visible)) {
        return { kind: "crane", aisle };
      }
    }
    const { origin, direction } = this.raycaster.ray;
    const location = pickCell(
      this.layout,
      { origin: origin.toArray(), direction: direction.toArray() },
      (candidate) => state.cell(candidate).load !== null,
    );
    return location ? { kind: "cell", location } : null;
  }

  /** Marks a 3D point as selected, or removes the mark when given null. */
  setHighlight(point) {
    this.highlight.visible = point !== null;
    if (point) {
      this.highlight.position.set(...point);
    }
  }

  /** Returns whether all corners of the warehouse are inside the camera's view. */
  boundsInView() {
    const { min, max } = this.bounds;
    this.camera.updateMatrixWorld();
    for (const x of [min[0], max[0]]) {
      for (const y of [min[1], max[1]]) {
        for (const z of [min[2], max[2]]) {
          const projected = new THREE.Vector3(x, y, z).project(this.camera);
          if (Math.abs(projected.x) > 1 || Math.abs(projected.y) > 1) {
            return false;
          }
        }
      }
    }
    return true;
  }

  placeLoad(load) {
    const key = locationKey(load.location);
    let slot = this.slotOfCell.get(key);
    if (slot === undefined) {
      slot = this.cellOfSlot.length;
      this.cellOfSlot.push(key);
      this.slotOfCell.set(key, slot);
    }
    const { center } = this.layout.cellBox(load.location);
    this.instanceMatrix.makeTranslation(center[0], center[1], center[2]);
    this.storedLoadUnits.setMatrixAt(slot, this.instanceMatrix);
    this.storedLoadUnits.setColorAt(slot, this.instanceColor.set(articleColor(load.article)));
  }

  removeLoad(location) {
    const key = locationKey(location);
    const slot = this.slotOfCell.get(key);
    if (slot === undefined) {
      return;
    }
    const lastSlot = this.cellOfSlot.length - 1;
    if (slot !== lastSlot) {
      this.storedLoadUnits.getMatrixAt(lastSlot, this.instanceMatrix);
      this.storedLoadUnits.setMatrixAt(slot, this.instanceMatrix);
      this.storedLoadUnits.getColorAt(lastSlot, this.instanceColor);
      this.storedLoadUnits.setColorAt(slot, this.instanceColor);
      const movedKey = this.cellOfSlot[lastSlot];
      this.cellOfSlot[slot] = movedKey;
      this.slotOfCell.set(movedKey, slot);
    }
    this.cellOfSlot.pop();
    this.slotOfCell.delete(key);
  }

  syncStoredLoadUnits(state) {
    const changes = state.takeChanges();
    if (changes.all) {
      this.slotOfCell.clear();
      this.cellOfSlot.length = 0;
      state.storedLoadUnits().forEach((load) => this.placeLoad(load));
    } else {
      for (const location of changes.cells) {
        const { load } = state.cell(location);
        if (load) {
          this.placeLoad(load);
        } else {
          this.removeLoad(location);
        }
      }
    }
    if (changes.all || changes.cells.length > 0) {
      this.storedLoadUnits.count = this.cellOfSlot.length;
      this.storedLoadUnits.instanceMatrix.needsUpdate = true;
      if (this.storedLoadUnits.instanceColor) {
        this.storedLoadUnits.instanceColor.needsUpdate = true;
      }
    }
  }

  updateCrane(aisle, state) {
    const view = state.crane(aisle);
    const crane = this.cranes.get(aisle);
    const [x, y, z] = this.layout.craneWorldPosition(aisle, view.position);
    crane.group.position.set(x, 0, z);
    crane.carriage.position.y = y;
    crane.material.color.set(activityColor(view.activity));
    const carried = view.carrying === null ? null : state.load(view.carrying);
    crane.carriedLoad.visible = carried !== null;
    if (carried) {
      crane.carriedLoad.material.color.set(articleColor(carried.article));
    }
  }

  update(state) {
    this.syncStoredLoadUnits(state);
    for (const aisle of this.cranes.keys()) {
      this.updateCrane(aisle, state);
    }
  }

  /** Turns the camera around the warehouse continuously, for benchmarks. */
  startOrbiting() {
    this.controls.autoRotate = true;
  }

  render() {
    this.controls.update();
    this.renderer.render(this.scene, this.camera);
  }

  info() {
    const { layout } = this;
    return {
      aisles: layout.aisleCount,
      racks: layout.aisleCount * layout.racksPerAisle,
      cells: layout.cellCount,
      cranes: this.cranes.size,
      transfer_points: this.transferPointCount,
      load_units: this.storedLoadUnits.count,
      article_colors: this.data.articles.map((_, index) => articleColor(index)),
    };
  }
}
