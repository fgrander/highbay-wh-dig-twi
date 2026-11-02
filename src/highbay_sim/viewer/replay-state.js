// The state of a run at a simulated time. There is one path to any state: events are applied in
// order up to the time, continuing forward or starting again when moving backward. The result
// therefore depends only on the time and the replay data, however that time was reached.

import { movementPosition } from "./motion.js";

const EVENT = {
  TIME: 0,
  KIND: 1,
  ORDER: 2,
  CRANE: 3,
  LOCATION: 4,
  ACTIVITY: 5,
  END: 6,
  START_POSITION: 7,
  TARGET_POSITION: 8,
};
const ORDER_ARTICLE = 2;

const locationKey = ([aisle, rack, bay, level]) => `${aisle}-${rack}-${bay}-${level}`;

function compareLocations(first, second) {
  for (let index = 0; index < first.length; index += 1) {
    if (first[index] !== second[index]) {
      return first[index] - second[index];
    }
  }
  return 0;
}

/** Returns the index of the last item starting at or before a time, or -1. */
function lastStartedIndex(items, time) {
  let low = 0;
  let high = items.length - 1;
  let found = -1;
  while (low <= high) {
    const middle = Math.floor((low + high) / 2);
    if (items[middle].start_s <= time) {
      found = middle;
      low = middle + 1;
    } else {
      high = middle - 1;
    }
  }
  return found;
}

class ReplayState {
  constructor(data) {
    this.data = data;
    const { layout, crane } = data.warehouse;
    this.craneParameters = crane;
    this.cellCount =
      layout.aisle_count * layout.racks_per_aisle * layout.bays_per_rack * layout.levels_per_rack;
    this.aisles = Array.from({ length: layout.aisle_count }, (_, index) => index + 1);
    this.activities = new Map(this.aisles.map((aisle) => [aisle, []]));
    this.movements = new Map(this.aisles.map((aisle) => [aisle, []]));
    for (const row of data.events) {
      if (row[EVENT.KIND] === "activity_started") {
        this.indexActivity(row);
      }
    }
    this.reset();
  }

  indexActivity(row) {
    const crane = row[EVENT.CRANE];
    this.activities.get(crane).push({
      start_s: row[EVENT.TIME],
      end_s: row[EVENT.END],
      activity: row[EVENT.ACTIVITY],
      order: row[EVENT.ORDER],
    });
    if (row[EVENT.START_POSITION] !== null) {
      this.movements.get(crane).push({
        start_s: row[EVENT.TIME],
        end_s: row[EVENT.END],
        start_position: row[EVENT.START_POSITION],
        target_position: row[EVENT.TARGET_POSITION],
      });
    }
  }

  reset() {
    this.time = 0;
    this.nextEvent = 0;
    this.cells = new Map();
    this.loads = new Map();
    this.carried = new Map(this.aisles.map((aisle) => [aisle, null]));
    this.waitingOrders = new Set();
    this.backlogTotal = 0;
    this.backlogPerAisle = new Map(this.aisles.map((aisle) => [aisle, 0]));
    this.completed = 0;
    this.arrived = 0;
    this.unfulfillable = 0;
    this.occupied = 0;
    this.changedCells = new Map();
    this.allChanged = true;
    this.data.initial_stock.forEach(([aisle, rack, bay, level, article], index) => {
      const location = [aisle, rack, bay, level];
      const load = {
        key: `i${index}`,
        article,
        store_order: null,
        retrieve_order: null,
        location,
        crane: null,
      };
      this.loads.set(load.key, load);
      this.cells.set(locationKey(location), { state: "occupied", load: load.key });
      this.occupied += 1;
    });
    this.applyEventsUpTo(0);
  }

  markChanged(location) {
    this.changedCells.set(locationKey(location), location);
  }

  applyEventsUpTo(time) {
    const { events } = this.data;
    while (this.nextEvent < events.length && events[this.nextEvent][EVENT.TIME] <= time) {
      this.apply(events[this.nextEvent]);
      this.nextEvent += 1;
    }
  }

  apply(row) {
    const order = row[EVENT.ORDER];
    const crane = row[EVENT.CRANE];
    const location = row[EVENT.LOCATION];
    switch (row[EVENT.KIND]) {
      case "order_arrived":
        this.arrived += 1;
        this.backlogTotal += 1;
        break;
      case "order_waiting_for_cell":
        this.waitingOrders.add(order);
        break;
      case "order_queued":
        this.waitingOrders.delete(order);
        this.backlogPerAisle.set(crane, this.backlogPerAisle.get(crane) + 1);
        this.reserveCell(order, location);
        break;
      case "order_started":
        this.backlogTotal -= 1;
        this.backlogPerAisle.set(crane, this.backlogPerAisle.get(crane) - 1);
        break;
      case "order_unfulfillable":
        this.backlogTotal -= 1;
        this.unfulfillable += 1;
        break;
      case "load_picked":
        this.pickLoad(order, crane, location);
        break;
      case "load_set":
        this.setLoad(crane, location);
        break;
      case "order_completed":
        this.completed += 1;
        break;
      default:
        break;
    }
  }

  reserveCell(order, location) {
    const key = locationKey(location);
    const cell = this.cells.get(key);
    if (cell) {
      cell.state = "reserved_for_retrieval";
      this.loads.get(cell.load).retrieve_order = order;
    } else {
      this.cells.set(key, { state: "reserved_for_storage", load: null });
    }
    this.markChanged(location);
  }

  pickLoad(order, crane, location) {
    if (location === null) {
      const load = {
        key: `o${order}`,
        article: this.data.orders[order][ORDER_ARTICLE],
        store_order: order,
        retrieve_order: null,
        location: null,
        crane,
      };
      this.loads.set(load.key, load);
      this.carried.set(crane, load.key);
      return;
    }
    const key = locationKey(location);
    const load = this.loads.get(this.cells.get(key).load);
    load.location = null;
    load.crane = crane;
    this.carried.set(crane, load.key);
    this.cells.delete(key);
    this.occupied -= 1;
    this.markChanged(location);
  }

  setLoad(crane, location) {
    const load = this.loads.get(this.carried.get(crane));
    this.carried.set(crane, null);
    if (location === null) {
      this.loads.delete(load.key);
      return;
    }
    load.location = location;
    load.crane = null;
    this.cells.set(locationKey(location), { state: "occupied", load: load.key });
    this.occupied += 1;
    this.markChanged(location);
  }

  /** Moves to a simulated time, which stays within the run. */
  moveTo(time) {
    const clamped = Math.min(Math.max(time, 0), this.data.run.duration_s);
    if (clamped < this.time) {
      this.reset();
    }
    this.applyEventsUpTo(clamped);
    this.time = clamped;
  }

  crane(aisle) {
    const activities = this.activities.get(aisle);
    const index = lastStartedIndex(activities, this.time);
    const current = index >= 0 && this.time < activities[index].end_s ? activities[index] : null;
    const movements = this.movements.get(aisle);
    const movementIndex = lastStartedIndex(movements, this.time);
    const movement = movementIndex >= 0 ? movements[movementIndex] : null;
    return {
      aisle,
      activity: current ? current.activity : "idle",
      order: current ? current.order : null,
      carrying: this.carried.get(aisle),
      position: movement
        ? movementPosition(movement, this.craneParameters, this.time)
        : [...this.data.warehouse.crane_start_positions[aisle]],
      movement_target:
        current && movement && current.start_s === movement.start_s
          ? [...movement.target_position]
          : null,
    };
  }

  cell(location) {
    const cell = this.cells.get(locationKey(location));
    return {
      location: [...location],
      state: cell ? cell.state : "free",
      load: cell && cell.load ? { ...this.loads.get(cell.load) } : null,
    };
  }

  load(key) {
    const load = this.loads.get(key);
    return load ? { ...load } : null;
  }

  /** Returns load units held in cells, in location order. */
  storedLoadUnits() {
    return [...this.loads.values()]
      .filter((load) => load.location !== null)
      .map((load) => ({ ...load }))
      .sort((first, second) => compareLocations(first.location, second.location));
  }

  summary() {
    const per_aisle = {};
    const cranes = {};
    for (const aisle of this.aisles) {
      per_aisle[aisle] = this.backlogPerAisle.get(aisle);
      cranes[aisle] = this.crane(aisle);
    }
    return {
      time_s: this.time,
      in_measurement_window: this.time >= this.data.run.window.start_s,
      backlog: {
        total: this.backlogTotal,
        per_aisle,
        waiting_for_cell: this.waitingOrders.size,
      },
      occupied_cells: this.occupied,
      occupancy: this.occupied / this.cellCount,
      completed: this.completed,
      arrived: this.arrived,
      unfulfillable: this.unfulfillable,
      cranes,
    };
  }

  stateAt(time) {
    this.moveTo(time);
    return this.summary();
  }

  /** Returns the cells changed since the last call, for updating only what needs drawing. */
  takeChanges() {
    const changes = { all: this.allChanged, cells: [...this.changedCells.values()] };
    this.changedCells = new Map();
    this.allChanged = false;
    return changes;
  }
}

export function createReplayState(data) {
  return new ReplayState(data);
}
