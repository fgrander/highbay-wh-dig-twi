// Controls, figures, and messages. Text from replay files is only ever set as text.

import { activityColor, articleColor } from "./appearance.js";

const element = (id) => document.getElementById(id);

function formatTime(seconds) {
  const whole = Math.floor(seconds);
  const parts = [Math.floor(whole / 3600), Math.floor((whole % 3600) / 60), whole % 60];
  const clock = parts.map((part) => String(part).padStart(2, "0")).join(":");
  return `${clock} (${seconds.toFixed(1)} s)`;
}

function legendEntry(label, color) {
  const entry = document.createElement("li");
  const swatch = document.createElement("span");
  swatch.className = "swatch";
  swatch.style.backgroundColor = color;
  entry.append(swatch, document.createTextNode(label));
  return entry;
}

export function showBenchmark({ average_fps, slowest_frame_ms }) {
  const box = element("benchmark");
  box.textContent =
    `Benchmark: ${average_fps.toFixed(1)} frames per second on average, ` +
    `slowest frame ${slowest_frame_ms.toFixed(0)} ms`;
  box.hidden = false;
}

export function showError(message) {
  document.body.classList.add("failed");
  const box = element("error");
  box.textContent = message;
  box.hidden = false;
}

const ORDER = { ID: 0, TYPE: 1, ARTICLE: 2, ARRIVAL: 3, START: 4, COMPLETION: 5, LOCATION: 7, END: 8 };

const ACTIVITY_LABELS = [
  ["moving_empty", "Moving empty"],
  ["moving_loaded", "Moving loaded"],
  ["handling", "Handling"],
  ["idle", "Idle"],
];
const OCCUPANCY_DECIMALS = 6;

function setText(id, text) {
  const target = element(id);
  if (target.textContent !== text) {
    target.textContent = text;
  }
}

const locationText = (location) => location.join("-");
const timeText = (value) => (value === null ? "not available" : `${value.toFixed(3)} s`);

function craneDestination(view, order) {
  if (view.movement_target === null) {
    return null;
  }
  const goesToCell =
    (order[ORDER.TYPE] === "storage") === (view.activity === "moving_loaded");
  return goesToCell ? `cell ${locationText(order[ORDER.LOCATION])}` : `${order[ORDER.END]} end`;
}

function craneDetails(data, state, aisle) {
  const view = state.crane(aisle);
  const lines = [`Crane ${aisle}`, `Activity: ${view.activity.replace("_", " ")}`];
  if (view.order !== null) {
    const order = data.orders[view.order];
    lines.push(`Order: ${order[ORDER.ID]}`);
    const destination = craneDestination(view, order);
    if (destination) {
      lines.push(`Destination: ${destination}`);
    }
  }
  if (view.carrying !== null) {
    const load = state.load(view.carrying);
    lines.push(`Carrying: ${data.articles[load.article]}`);
  }
  return { lines, carried: view.carrying };
}

function orderLines(data, label, index) {
  const order = data.orders[index];
  return [
    `${label}: ${order[ORDER.ID]}`,
    `Arrival: ${timeText(order[ORDER.ARRIVAL])}`,
    `Start: ${timeText(order[ORDER.START])}`,
    `Completion: ${timeText(order[ORDER.COMPLETION])}`,
  ];
}

function loadDetails(data, state, key) {
  const load = state.load(key);
  const lines = [`Load unit: ${data.articles[load.article]}`];
  lines.push(
    ...(load.store_order === null
      ? ["Origin: initial stock"]
      : orderLines(data, "Storage order", load.store_order)),
  );
  if (load.retrieve_order !== null) {
    lines.push(...orderLines(data, "Retrieval order", load.retrieve_order));
  }
  if (load.location) {
    const cell = state.cell(load.location);
    lines.push(`Cell: ${locationText(cell.location)}`, `Cell state: ${cell.state}`);
  } else {
    lines.push(`On: Crane ${load.crane}`);
  }
  return { lines, carried: null };
}

function cellDetails(state, location) {
  const cell = state.cell(location);
  return {
    lines: [`Cell: ${locationText(cell.location)}`, `Cell state: ${cell.state}`],
    carried: null,
  };
}

function describe(data, state, selection) {
  if (selection === null) {
    return { lines: [], carried: null };
  }
  if (selection.kind === "crane") {
    return craneDetails(data, state, selection.aisle);
  }
  return selection.kind === "load"
    ? loadDetails(data, state, selection.key)
    : cellDetails(state, selection.location);
}

export function createPanels({
  data,
  speeds,
  initialSpeed,
  onTogglePlay,
  onRestart,
  onMove,
  onSpeed,
  onDefaultView,
  onSelectCarried,
  onGoToPeak,
}) {
  const detailsBox = element("details");
  let shownDetails = null;
  const play = element("play");
  const slider = element("time-slider");
  const speed = element("speed");
  const timeLabel = element("time-label");

  slider.max = String(data.run.duration_s);
  for (const value of speeds) {
    const option = document.createElement("option");
    option.value = String(value);
    option.textContent = `${value}×`;
    speed.append(option);
  }
  speed.value = String(initialSpeed);

  element("legend").append(
    ...data.articles.map((article, index) => legendEntry(article, articleColor(index))),
  );

  element("crane-legend").append(
    ...ACTIVITY_LABELS.map(([activity, label]) => legendEntry(label, activityColor(activity))),
  );

  const { run } = data;
  element("run-identification").replaceChildren(
    ...[
      `Warehouse: ${run.warehouse.name}`,
      `Scenario: ${run.scenario.name}`,
      `Seed: ${run.seed}`,
      `Software version: ${run.software_version}`,
    ].map((line) => {
      const row = document.createElement("div");
      row.textContent = line;
      return row;
    }),
  );

  const aisleRows = new Map();
  for (const aisle of Object.keys(data.warehouse.transfer_points)) {
    const row = document.createElement("li");
    aisleRows.set(aisle, row);
    element("figure-per-aisle").append(row);
  }

  play.addEventListener("click", onTogglePlay);
  element("go-to-peak").addEventListener("click", onGoToPeak);
  element("restart").addEventListener("click", onRestart);
  element("default-view").addEventListener("click", onDefaultView);
  slider.addEventListener("input", () => onMove(Number(slider.value)));
  speed.addEventListener("change", () => onSpeed(Number(speed.value)));
  document.body.classList.add("loaded");

  return {
    update({ time_s, playing }) {
      play.textContent = playing ? "Pause" : "Play";
      timeLabel.textContent = formatTime(time_s);
      if (document.activeElement !== slider || playing) {
        slider.value = String(time_s);
      }
    },
    updateFigures(summary) {
      setText("figure-window", summary.in_measurement_window ? "Measurement window" : "Warm-up");
      setText("figure-backlog", String(summary.backlog.total));
      setText("figure-waiting", String(summary.backlog.waiting_for_cell));
      setText("figure-occupancy", summary.occupancy.toFixed(OCCUPANCY_DECIMALS));
      setText("figure-completed", String(summary.completed));
      setText("figure-unfulfillable", String(summary.unfulfillable));
      for (const [aisle, row] of aisleRows) {
        const text = `Aisle ${aisle}: ${summary.backlog.per_aisle[aisle]}`;
        if (row.textContent !== text) {
          row.textContent = text;
        }
      }
    },
    /** Shows a selection's details, changing the page only when they change. */
    updateDetails(state, selection) {
      const { lines, carried } = describe(data, state, selection);
      const key = JSON.stringify([lines, carried]);
      if (key === shownDetails) {
        return;
      }
      shownDetails = key;
      detailsBox.replaceChildren(
        ...lines.map((line) => {
          const row = document.createElement("div");
          row.textContent = line;
          return row;
        }),
      );
      if (carried !== null) {
        const button = document.createElement("button");
        button.id = "select-carried";
        button.type = "button";
        button.textContent = "Select carried load unit";
        button.addEventListener("click", () => onSelectCarried(carried));
        detailsBox.append(button);
      }
    },
  };
}
