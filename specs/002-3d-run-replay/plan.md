# Implementation Plan: 3D Run Replay

**Branch**: `002-3d-run-replay` | **Date**: 2026-11-01 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/002-3d-run-replay/spec.md`

## Summary

Add an optional replay file to simulation runs, and a browser-based 3D viewer that plays it. `highbay-sim run --replay` writes `replay.json` from the events the simulation already produces, leaving result files byte-identical. `highbay-sim view` starts a read-only local web server and opens the viewer, which is plain JavaScript with a copy of three.js in the repository, so it needs no build step and no internet connection. See [research.md](research.md) for the decisions behind this approach.

## Technical Context

**Language/Version**: Python 3.12 or newer for the simulation, replay writer, and local server. JavaScript (ES modules, no build step) for the viewer, as decided in the spec's browser requirement.

**Primary Dependencies**: three.js 0.170.0, copied into the repository. No new Python runtime dependencies; the local server uses the standard library.

**Storage**: Files only: `replay.json` next to the existing outputs

**Testing**: pytest for Python. pytest with Playwright and headless Chromium for viewer logic and behavior, as a development dependency only. Documented manual steps for what automated tests cannot measure, such as frame rate on real graphics hardware.

**Target Platform**: Windows 11 with a current Chromium-based browser or Firefox, both with WebGL 2

**Project Type**: Existing library and command-line interface, extended with a local web viewer

**Performance Goals**: At 20 aisles, 100,000 cells, and 24 simulated hours at 1,000 orders per hour: at least 30 frames per second (SC-002), moving to any time in under 1 second (SC-003), replay data of at most 100 MB, and at most 30 seconds added to the run (SC-008)

**Constraints**: No internet connection at viewing time; viewer reads only; server reachable only from the same computer; simulation results unchanged (FR-002); simulation remains free of display dependencies (FR-005)

**Scale/Scope**: One run at a time; about 165,000 events and 100,000 cells at the planning target

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle or rule | How this plan complies | Pre-design | Post-design |
|---|---|---|---|
| I. Simulation core independent of visualization | The viewer only reads a saved file. `simulate` gains no user interface dependency, and its new event fields are only descriptive. | PASS | PASS |
| II. Reproducible simulation | Replay files are byte-identical for identical inputs. Playback uses its own clock and never affects results. | PASS | PASS |
| III. Credible throughput results | Replay data carries the same hashes and reported metrics as the results, and tests compare the viewer's figures with them. Motion is verified against hand calculations. | PASS | PASS |
| IV. Live data as a later, pluggable option | No live connection is built. The server only serves files, on the local computer, and accepts only read requests. | PASS | PASS |
| V. Test-first simulation logic | Replay writing and viewer state logic are written test-first. Rendering has automated tests where practical and documented manual steps otherwise ([quickstart.md](quickstart.md)). | PASS | PASS |
| VI. Incremental delivery and simplicity | Each story can be demonstrated. Added complexity is justified below. | PASS | PASS |
| Technical constraints | Performance targets are stated, and the stack is chosen here. No credentials are involved. | PASS | PASS |
| Development workflow | Spec Kit sequence on a feature branch. This feature must not alter simulation results, and a test enforces this. | PASS | PASS |

No violations.

## Project Structure

### Documentation (this feature)

```text
specs/002-3d-run-replay/
├── plan.md              # This file
├── research.md          # Technical decisions and rationale
├── data-model.md        # Layout, motion, and state derivation
├── quickstart.md        # Validation scenarios and manual steps
├── contracts/
│   ├── cli.md           # New and changed commands
│   ├── replay-format.md # replay.json
│   └── viewer.md        # Viewer behavior and module boundaries
├── checklists/
│   └── requirements.md  # Specification quality checklist
└── tasks.md             # Created by /speckit-tasks
```

### Source Code (repository root)

```text
src/highbay_sim/
├── cli.py               # Changed: run --replay, new view command
├── events.py            # Changed: movement start and target positions
├── engine.py            # Changed: fills those positions
├── outputs.py           # Changed: replay.json counts as an output file
├── replay.py            # New: builds and writes replay data
├── viewer_server.py     # New: read-only local server
└── viewer/              # New: included in the Python package
    ├── index.html
    ├── style.css
    ├── main.js          # Starts the viewer and connects its parts
    ├── replay-file.js   # Loads and checks replay data
    ├── replay-state.js  # State at a simulated time
    ├── motion.js        # Crane position at a time
    ├── layout.js        # 3D positions of warehouse objects
    ├── playback.js      # Simulated clock and speed
    ├── picking.js       # Finds what a selection hits
    ├── scene.js         # Draws state using appearance.js
    ├── appearance.js    # Shapes and colors of each object type
    ├── panels.js        # Controls, figures, and details
    └── vendor/          # three.js 0.170.0 and its license

tests/
├── unit/                # Changed and new: replay writing
├── integration/         # Changed and new: CLI and server
├── verification/        # New: hand-calculated crane positions
├── viewer/              # New: Playwright tests of viewer logic and behavior
└── performance/         # Changed: SC-008 and SC-003

samples/
└── replay/              # New: warehouse with an overloaded aisle for User Story 3
```

**Structure Decision**: The viewer stays inside the existing Python package, so `uv sync` installs everything and the viewer works without a separate install or build step.

## Complexity Tracking

| Addition | Why Needed | Simpler Alternative Rejected Because |
|----------|------------|--------------------------------------|
| JavaScript as a second language | The project owner chose a viewer in the web browser, and browsers run JavaScript for 3D | Python compiled for the browser is slower and adds a large download, which conflicts with SC-002 |
| A copy of three.js in the repository | Required by the no-internet requirement, and it avoids writing a 3D engine | Loading it from the internet fails offline, and direct WebGL means far more code |
| Playwright as a development dependency | Viewer logic needs automated tests (Principle V), and Node.js is not installed | Installing Node.js adds a second toolchain, and only manual testing would miss state errors |
| A local web server | Browsers block JavaScript modules and file loading from `file://` addresses | Embedding all data and code in one HTML file makes large replay files slow to open, and the logic harder to test |
