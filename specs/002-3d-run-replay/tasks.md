---

description: "Task list for the 3D run replay"
---

# Tasks: 3D Run Replay

**Input**: Design documents from `specs/002-3d-run-replay/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included. Constitution Principle V requires test-first development for replay and state logic, and automated tests for visualization code where practical. Principle III requires verification against independently known results.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- All paths are relative to the repository root
- `viewer/` means `src/highbay_sim/viewer/`, and `contracts/` means `specs/002-3d-run-replay/contracts/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Dependencies and the copy of three.js

- [ ] T001 Change the version to `0.2.0` in `pyproject.toml` and `src/highbay_sim/__init__.py`, add `playwright` as a dev dependency, add a `viewer` pytest marker in `pyproject.toml`, run `uv sync`, and run `uv run playwright install chromium`; do not add runtime dependencies
- [ ] T002 [P] Download three.js 0.170.0 from `https://unpkg.com/three@0.170.0/`: `build/three.module.min.js` and any file it imports, `examples/jsm/controls/OrbitControls.js`, and `LICENSE`, into `src/highbay_sim/viewer/vendor/`; create `src/highbay_sim/viewer/vendor/README.md` recording the version, source addresses, and SHA-256 of each file

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Replay files, the local server, and the viewer test setup that every user story needs

**CRITICAL**: No user story work can begin until this phase is complete. Write each test task first and confirm that it fails before its implementation task.

- [ ] T003 [P] Add failing tests to `tests/unit/test_engine.py`: `activity_started` events for `moving_empty` and `moving_loaded` have correct `start_position` and `target_position`, including a zero-length move; `handling` events and all other kinds have `None` for both
- [ ] T004 [P] Write failing tests in `tests/unit/test_replay.py` for `contracts/replay-format.md`, using a V1-style run: all top-level parts; `format_version` is 1; `run` equals the `run` block of `result.json`; `initial_stock` rows are sorted and use article indexes; `orders` and `events` rows follow their column lists, with 3-decimal times and `null` for empty values; `crane_start_positions` and `transfer_points` have one entry per aisle, including overrides; `reported` equals the values in `result.json`; `first_backlog_peak_s` is correct when the peak is inside the window, when it is carried in from before the window, when several times share the maximum, and when backlog is always zero (then it equals the window start)
- [ ] T005 [P] Write failing tests in `tests/integration/test_replay_cli.py` for `contracts/cli.md`: `--replay` writes `replay.json`; without it, none is written; `report.md`, `result.json`, and `orders.csv` are byte-identical with and without it; two runs in processes with different `PYTHONHASHSEED` give byte-identical `replay.json`; the file has no `\r`, no machine details, and is compact; an existing `replay.json` needs `--overwrite` when `--replay` is given; a run needs no display and loads no graphical module; `view` with a missing path or a directory without `replay.json` exits with code 2 and a message
- [ ] T006 [P] Write failing tests in `tests/integration/test_viewer_server.py`: the server binds only to `127.0.0.1`; GET and HEAD work for viewer files and for `/replay.json`; `.js` is served as `text/javascript`, `.html` as `text/html`, `.css` as `text/css`, and `.json` as `application/json`, whatever the system's registered types are; POST, PUT, and DELETE are refused and change no file; paths outside the viewer directory, including encoded `..`, are refused, and the only replay file served is the chosen one; a damaged replay file is still served unchanged, as the viewer reports the problem
- [ ] T007 Add `start_position` and `target_position` with default `None` to `SimulationEvent` in `src/highbay_sim/events.py`, and fill them for movements in `src/highbay_sim/engine.py` (depends on T003); make no other change to engine behavior
- [ ] T008 Implement `build_replay` and `write_replay` in `src/highbay_sim/replay.py` (depends on T004, T007): build the structure in `contracts/replay-format.md` from `RunRecord`, the warehouse definition, `RunInfo`, and `Metrics`, write it with compact separators, a final newline, and Unix line endings, and calculate `first_backlog_peak_s` using the same grouping of equal-time events as `_backlog` in `src/highbay_sim/metrics.py`
- [ ] T009 Add the `--replay` option to `run` in `src/highbay_sim/cli.py`, and treat `replay.json` as an existing output only when `--replay` is given (depends on T005, T008)
- [ ] T010 Create a minimal `viewer/index.html`, and implement `src/highbay_sim/viewer_server.py` (depends on T006): a `ThreadingHTTPServer` bound to `127.0.0.1` with a free or chosen port, read-only handling of GET and HEAD, explicit content types, and `/replay.json` mapped to the chosen file. Add the `view` command with `--port` and `--no-browser` to `src/highbay_sim/cli.py` with the behavior and exit codes in `contracts/cli.md`, including exit code 0 on Ctrl+C
- [ ] T011 Create `tests/viewer/conftest.py` (depends on T010): session fixtures that start `viewer_server` for a chosen replay file and open a headless Chromium page with WebGL through software rendering; a helper that imports a viewer module into the page and calls it; a helper that runs a sample through the CLI with `--replay`. Mark all tests in `tests/viewer/` with the `viewer` marker, and make a missing Chromium a clear failure, not a skip

**Checkpoint**: `replay.json` is written and served, and viewer modules can be tested in a browser.

---

## Phase 3: User Story 1 - Watch a Run Replay in 3D (Priority: P1) 🎯 MVP

**Goal**: A planner opens a completed run, sees the warehouse in 3D, and plays it with pause, speed, restart, and moving to any time.

**Independent Test**: Run a sample with `--replay`, open it, play it, and confirm that crane positions and stored load units match per-order results at chosen times (`quickstart.md` Scenarios 1, 2, 3, 4, 7, and 8).

### Tests for User Story 1 ⚠️

> **NOTE: Write these tests FIRST, and ensure they FAIL before implementation**

- [ ] T012 [P] [US1] Write failing tests in `tests/viewer/test_motion.py` with values worked out in `quickstart.md` Scenario 3 and in comments: all phases in the `data-model.md` table for both profile types; both directions; zero distance; times before the start and after the axis's own time; and an axis finished early holding its target until `end_s`
- [ ] T013 [P] [US1] Write failing tests in `tests/viewer/test_replay_file.py`: a valid file loads; a failed request, invalid JSON, a truncated file, `format_version` 999 with a message naming both versions, and each missing required part (`run`, `warehouse`, `articles`, `initial_stock`, `orders`, `events`, `reported`) all give a clear error and no data
- [ ] T014 [P] [US1] Write failing tests in `tests/viewer/test_layout.py` for each row of the 3D layout table in `data-model.md`, with values worked out by hand: cell box position and size, aisle center, rack 1 and rack 2 position, one rack per aisle, block width, block gap, aisle ends, and overall bounds used for the default view
- [ ] T015 [P] [US1] Write failing tests in `tests/viewer/test_replay_state.py` for each row of the Replay State table in `data-model.md`: the V1 load unit times in `quickstart.md` Scenario 3; cell states following "free --> reserved_for_storage --> occupied --> reserved_for_retrieval --> free"; only `occupied` and `reserved_for_retrieval` cells hold a drawn load unit; "Zero-length activities are never current"; total backlog always equal to per-aisle backlog plus orders waiting for a cell; all events at a time applied together; a run with no orders; an unfinished order stopping at the end of the run; an unfulfillable order moving nothing and being counted; a waiting storage order counted without a load unit
- [ ] T016 [P] [US1] Write failing tests in `tests/viewer/test_state_consistency.py` using `samples/small-warehouse.yaml` and `samples/daily-scenario.yaml`: for at least 200 times, moving directly to a time, moving backward to it from later, and reaching it in small forward steps give identical crane positions, stored load units, and counts (SC-005); end-of-run completed orders, backlog, and occupancy equal `reported` and `report.md` (SC-006)
- [ ] T017 [P] [US1] Write failing tests in `tests/viewer/test_playback.py` with an injected clock: "Always within 0 and the run's duration"; "Stops at the end of the run"; speeds exactly 1, 10, 60, 600, and 3,600; initial values "time 0, paused, speed 60"; simulated time equals real time multiplied by speed; changing speed keeps the current time; restart goes to time 0 and pauses; moving beyond either end stays within the run
- [ ] T018 [P] [US1] Write failing tests in `tests/viewer/test_replay_ui.py` through the interface and `window.highbayViewer`: the scene has the right aisles, racks, cells, transfer points, one crane per aisle, and initial stock; play advances time and moves a crane; pause, restart, speed, and the time slider work; each damaged replay file shows a message and no warehouse (FR-009); missing WebGL 2 shows a message; every network request goes only to the local server (offline requirement); a viewing session leaves all run files byte-identical; articles have distinct colors and a legend; `ready` resolves in both the loaded and error cases
- [ ] T019 [P] [US1] Write tests in `tests/verification/test_crane_positions.py` that open `samples/verification/v1-warehouse.yaml` with `v1-scenario.yaml` in the viewer and check within 1 cm each position in the `quickstart.md` Scenario 3 table, and each load unit time listed there (SC-004); show the calculation in comments

### Implementation for User Story 1

- [ ] T020 [P] [US1] Implement `viewer/motion.js` (depends on T012) with the formulas in `data-model.md`
- [ ] T021 [P] [US1] Implement `viewer/replay-file.js` (depends on T013): load and check replay data; never use a file that fails a check
- [ ] T022 [P] [US1] Implement `viewer/layout.js` (depends on T014) with no document or three.js use
- [ ] T023 [US1] Implement `stateAt(time)` in `viewer/replay-state.js` (depends on T015, T016, T020): one path that applies events up to a time, continuing forward from the current state and starting again from the initial state when moving backward; each crane's activities searched by time; no document or three.js use
- [ ] T024 [P] [US1] Implement `viewer/playback.js` (depends on T017) with an injectable clock and no document use
- [ ] T025 [P] [US1] Implement `viewer/appearance.js` as the only module deciding how objects look: one function per object type (rack, load unit, crane, transfer point) that creates simple shapes from dimensions, and article colors from a fixed sequence in `articles` order
- [ ] T026 [US1] Implement `viewer/scene.js` (depends on T022, T025): draw each rack as its frame only, load units as one instanced mesh with capacity for all cells, updating only instances that changed; cranes and transfer points as individual objects; a fixed default camera showing the whole warehouse
- [ ] T027 [US1] Implement `viewer/panels.js` for playback controls, simulated time, article legend, and error message, and complete `viewer/index.html` and `viewer/style.css` for a layout usable at common desktop sizes
- [ ] T028 [US1] Implement `viewer/main.js` (depends on T021, T023, T024, T026, T027): connect the parts, run the frame loop, check WebGL 2, and expose read-only `window.highbayViewer` as in `contracts/viewer.md`

**Checkpoint**: User Story 1 works. All tests from T012 to T019 pass, and `quickstart.md` Scenarios 1, 2, 3, 4, 7, and 8 succeed.

---

## Phase 4: User Story 2 - Navigate and Inspect (Priority: P2)

**Goal**: A planner looks around from any angle, and selects a crane, cell, or load unit to see its details.

**Independent Test**: Open a run, move the camera, select objects at chosen times, and compare the details with per-order results (`quickstart.md` Scenario 5).

### Tests for User Story 2 ⚠️

> **NOTE: Write these tests FIRST, and ensure they FAIL before implementation**

- [ ] T029 [P] [US2] Write failing tests in `tests/viewer/test_picking.py` with values worked out by hand: a ray hits the expected cell for each rack side, bay, and level; a ray misses the racks; the nearest of several hit cells is chosen; empty cells can be hit; a ray through an aisle gap continues to the next rack
- [ ] T030 [P] [US2] Write failing tests in `tests/viewer/test_inspection_ui.py`: rotating, moving, and zooming do not change simulated time or playing state; the default view button makes the whole warehouse visible at any warehouse size; selecting a crane shows its number, activity, order, and destination; selecting a cell shows its location, state, and any article; selecting a load unit shows its article and order with times, and "initial stock" where it has no order; values match `orders.csv` at the chosen time and refresh as time changes; a selected load unit that no longer exists clears the selection

### Implementation for User Story 2

- [ ] T031 [US2] Implement `viewer/picking.js` (depends on T029): calculate the cell from the ray and layout, with no document or three.js use
- [ ] T032 [US2] Add camera controls with the copied `OrbitControls.js`, a default view action, ray creation from clicks, and tests against crane objects in `viewer/scene.js` (depends on T031)
- [ ] T033 [US2] Add selection handling and refresh in `viewer/main.js`, a highlight in `viewer/appearance.js`, and the details panel and default view button in `viewer/panels.js` and `viewer/index.html` (depends on T030, T032)

**Checkpoint**: User Stories 1 and 2 work. `quickstart.md` Scenario 5 succeeds.

---

## Phase 5: User Story 3 - Spot Bottlenecks During Replay (Priority: P3)

**Goal**: A planner sees which cranes are busy, where orders wait, and how figures develop, and can jump to the highest backlog.

**Independent Test**: Replay a run in which one aisle is overloaded, and confirm that crane states, per-aisle backlog, and figures show the imbalance and match the report (`quickstart.md` Scenario 6).

### Tests for User Story 3 ⚠️

> **NOTE: Write these tests FIRST, and ensure they FAIL before implementation**

- [ ] T034 [P] [US3] Create `samples/replay/overloaded-warehouse.yaml` and `samples/replay/busy-scenario.yaml`, with illustrative values, so that `nearest_free` overloads aisle 1 and a measurable backlog builds up in the measurement window
- [ ] T035 [P] [US3] Write failing tests in `tests/viewer/test_bottlenecks_ui.py` using the files from T034: crane colors match activity at chosen times, using "moving empty is blue, moving loaded is orange, handling is purple, and idle is gray", with a legend; figures show simulated time, warm-up or measurement window, total backlog, backlog per aisle, orders waiting for a cell, occupancy, orders completed, and the run's identification; aisle 1 shows more backlog than the others at the peak; at the end, displayed values equal `report.md`; "Go to highest backlog" moves to `first_backlog_peak_s`, pauses, and shows a total equal to `max_in_window`

### Implementation for User Story 3

- [ ] T036 [US3] Add activity colors to `viewer/appearance.js` and apply them in `viewer/scene.js` (depends on T035)
- [ ] T037 [US3] Add the figures, crane legend, and "Go to highest backlog" control to `viewer/panels.js` and `viewer/index.html`, and connect them in `viewer/main.js` (depends on T036)

**Checkpoint**: All user stories work. `quickstart.md` Scenario 6 succeeds.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Performance, documentation, and final validation

- [ ] T038 [P] Create `tests/performance/write_planning_target.py`, which writes results and `replay.json` for 20 aisles, 100,000 cells, and 24 simulated hours at 1,000 orders per hour to a directory given as its argument
- [ ] T039 Write `tests/performance/test_replay_performance.py` using T038: replay data is at most 100 MB, writing it adds at most 30 seconds (SC-008), and moving to the end, to the start, and to 20 other times each shows the correct state in under 1 second in headless Chromium (SC-003)
- [ ] T040 Add benchmark mode to `viewer/main.js` and `viewer/panels.js` as in `contracts/viewer.md`: at `?benchmark=1`, play at 600× for 20 seconds while the camera orbits, then display and expose the average frames per second and the slowest frame; add a test in `tests/viewer/test_replay_ui.py` that it completes and reports numbers, without asserting a frame rate
- [ ] T041 [P] Update `README.md` with `--replay`, `view`, viewer controls, supported browsers, viewer test setup, and how to replace shapes through `viewer/appearance.js`
- [ ] T042 [P] Add `start_position` and `target_position` to the Simulation Event description in `specs/001-headless-throughput-sim/data-model.md`
- [ ] T043 Run `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src`, and `uv run pytest`, and fix every problem reported; confirm that `ruff` left `.specify/` and `specs/` untouched
- [ ] T044 Run the automated and scripted scenarios in `specs/002-3d-run-replay/quickstart.md`, and record any difference from the expected results; list every manual step that remains for the project owner, including the SC-002 frame rate check and the SC-001 timing, rather than marking them as passed

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies
- **Foundational (Phase 2)**: Depends on Setup; blocks all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational
- **User Story 2 (Phase 4)**: Depends on User Story 1, because it inspects the scene and state
- **User Story 3 (Phase 5)**: Depends on User Story 1; independent of User Story 2 apart from edits to the same files
- **Polish (Phase 6)**: Depends on all stories; T038 and T039 need only User Story 1

### Within Each User Story

- Tests are written first and must fail before implementation
- Order within User Story 1: logic modules (T020 to T024) → appearance and scene (T025, T026) → panels (T027) → `main.js` (T028)
- Tasks T018 and T019 can pass only after T028, so they stay failing throughout User Story 1

### Parallel Opportunities

- Setup: T002 alongside T001
- Foundational: T003, T004, T005, T006 together
- User Story 1: T012 to T019 together; then T020, T021, T022, T024, T025 together
- User Story 2: T029, T030 together
- User Story 3: T034, T035 together
- Polish: T038, T041, T042 together

---

## Parallel Example: User Story 1

```text
Task: "Write failing tests in tests/viewer/test_motion.py"
Task: "Write failing tests in tests/viewer/test_replay_file.py"
Task: "Write failing tests in tests/viewer/test_layout.py"
Task: "Write failing tests in tests/viewer/test_replay_state.py"
Task: "Write failing tests in tests/viewer/test_playback.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Run `quickstart.md` Scenarios 1, 2, 3, 4, 7, and 8, and let the project owner look at the viewer

### Incremental Delivery

1. Setup + Foundational → replay files written and served
2. User Story 1 → replay plays in 3D (MVP)
3. User Story 2 → navigation and inspection
4. User Story 3 → bottleneck analysis
5. Polish → performance confirmed and documentation complete

---

## Notes

- [P] tasks use different files and have no dependencies on incomplete tasks
- Do not build anything listed as out of scope in `spec.md`, including detailed 3D models, live data, watching a run while it simulates, comparing runs, or video export
- This feature must not change simulation results. Mark any commit that does (constitution, Development Workflow), and treat it as a defect unless the spec is changed
- Do not add load from the internet at viewing time, including fonts and styles
- Frame rate and the time to first use cannot be confirmed by automated tests; report them as manual steps
- Stop at any checkpoint to validate a story independently
