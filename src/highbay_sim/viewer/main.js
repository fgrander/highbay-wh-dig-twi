// Starts the viewer and connects its parts. The viewer only reads replay data.

import { createLayout } from "./layout.js";
import { createPanels, showBenchmark, showError } from "./panels.js";
import { createPlayback, SPEEDS } from "./playback.js";
import { loadReplay } from "./replay-file.js";
import { createReplayState } from "./replay-state.js";
import { WarehouseScene } from "./scene.js";

const NO_WEBGL_MESSAGE =
  "This browser cannot show the 3D view, as WebGL 2 is not available. " +
  "Use a current browser, and check that hardware acceleration is enabled.";
const CLICK_LIMIT_PX = 4;
const BENCHMARK_SPEED = 600;
const BENCHMARK_SECONDS = 20;

let lastError = null;
let viewer = null;
let selection = null;
let benchmarkResult = null;

function hasWebGL2() {
  return document.createElement("canvas").getContext("webgl2") !== null;
}

function fail(message) {
  lastError = message;
  showError(message);
}

function createViewer(data) {
  const layout = createLayout(data.warehouse.layout);
  const state = createReplayState(data);
  const scene = new WarehouseScene(document.getElementById("view"), data, layout);
  const playback = createPlayback({ duration_s: data.run.duration_s });

  const highlightPoint = () => {
    if (selection === null) {
      return null;
    }
    if (selection.kind === "crane") {
      return scene.craneCarriagePoint(selection.aisle);
    }
    if (selection.kind === "cell") {
      return layout.cellBox(selection.location).center;
    }
    const load = state.load(selection.key);
    return load.location
      ? layout.cellBox(load.location).center
      : scene.craneCarriagePoint(load.crane);
  };

  const refresh = () => {
    state.moveTo(playback.time_s);
    scene.update(state);
    panels.update(playback);
    panels.updateFigures(state.summary());
    if (selection?.kind === "load" && state.load(selection.key) === null) {
      selection = null;
    }
    panels.updateDetails(state, selection);
    scene.setHighlight(highlightPoint());
  };

  const select = (hit) => {
    selection = hit;
    if (hit?.kind === "cell") {
      const { load } = state.cell(hit.location);
      if (load) {
        selection = { kind: "load", key: load.key };
      }
    }
    refresh();
  };

  const panels = createPanels({
    data,
    speeds: SPEEDS,
    initialSpeed: playback.speed,
    onTogglePlay: () => {
      if (playback.playing) {
        playback.pause();
      } else {
        playback.play();
      }
      refresh();
    },
    onRestart: () => {
      playback.restart();
      refresh();
    },
    onMove: (time) => {
      playback.moveTo(time);
      refresh();
    },
    onSpeed: (speed) => playback.setSpeed(speed),
    onDefaultView: () => scene.showWholeWarehouse(),
    onSelectCarried: (key) => select({ kind: "load", key }),
    onGoToPeak: () => {
      playback.pause();
      playback.moveTo(data.reported.first_backlog_peak_s);
      refresh();
    },
  });

  let pressed = null;
  scene.canvas.addEventListener("pointerdown", (event) => {
    pressed = event.button === 0 ? [event.clientX, event.clientY] : null;
  });
  scene.canvas.addEventListener("pointerup", (event) => {
    if (pressed && Math.hypot(event.clientX - pressed[0], event.clientY - pressed[1]) < CLICK_LIMIT_PX) {
      select(scene.pickAt(event.clientX, event.clientY, state));
    }
    pressed = null;
  });

  refresh();
  const frame = () => {
    playback.update();
    refresh();
    scene.render();
    requestAnimationFrame(frame);
  };
  requestAnimationFrame(frame);
  return { data, state, scene, playback };
}

/** Plays while the camera orbits, then reports the frame rate. */
function runBenchmark({ scene, playback }, seconds) {
  playback.setSpeed(BENCHMARK_SPEED);
  playback.play();
  scene.startOrbiting();
  const started = performance.now();
  let previous = started;
  let frames = 0;
  let slowest = 0;
  const measure = () => {
    const now = performance.now();
    slowest = Math.max(slowest, now - previous);
    previous = now;
    frames += 1;
    if (now - started < seconds * 1000) {
      requestAnimationFrame(measure);
      return;
    }
    benchmarkResult = {
      frames,
      seconds: (now - started) / 1000,
      average_fps: (frames * 1000) / (now - started),
      slowest_frame_ms: slowest,
    };
    showBenchmark(benchmarkResult);
  };
  requestAnimationFrame(measure);
}

async function start() {
  const { data, error } = await loadReplay("/replay.json");
  if (error) {
    fail(error);
    return;
  }
  if (!hasWebGL2()) {
    fail(NO_WEBGL_MESSAGE);
    return;
  }
  try {
    viewer = createViewer(data);
    const parameters = new URLSearchParams(window.location.search);
    if (parameters.get("benchmark") === "1") {
      runBenchmark(viewer, Number(parameters.get("seconds") ?? BENCHMARK_SECONDS));
    }
  } catch (problem) {
    fail(`The replay could not be shown: ${problem.message}`);
  }
}

const ready = start();

// Read-only access for automated tests and benchmarks.
window.highbayViewer = Object.freeze({
  ready,
  get lastError() {
    return lastError;
  },
  get time_s() {
    return viewer.playback.time_s;
  },
  get playing() {
    return viewer.playback.playing;
  },
  get speed() {
    return viewer.playback.speed;
  },
  get duration_s() {
    return viewer.playback.duration_s;
  },
  get selection() {
    return selection === null ? null : { ...selection };
  },
  get benchmark() {
    return benchmarkResult === null ? null : { ...benchmarkResult };
  },
  get reportedPeak() {
    return viewer.data.reported.first_backlog_peak_s;
  },
  craneColor: (aisle) => viewer.scene.craneColor(aisle),
  cameraPosition: () => viewer.scene.cameraPosition(),
  craneScreenPosition: (aisle) => viewer.scene.craneScreenPosition(aisle),
  cellScreenPosition: (location) => viewer.scene.cellScreenPosition(location),
  summary: () => viewer.state.summary(),
  crane: (aisle) => viewer.state.crane(aisle),
  cell: (location) => viewer.state.cell(location),
  storedLoadUnits: () => viewer.state.storedLoadUnits(),
  sceneInfo: () => viewer.scene.info(),
  boundsInView: () => viewer.scene.boundsInView(),
  renderNow: () => viewer.scene.render(),
});
