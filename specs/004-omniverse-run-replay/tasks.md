---

description: "Task list for the Omniverse run replay"
---

# Tasks: Omniverse Run Replay

**Input**: Design documents from `specs/004-omniverse-run-replay/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included. Constitution Principle V requires automated tests for visualization where practical, and documented manual steps otherwise. The logic in `core/` is written test-first.

**Test-first rule**: For each test task on `core/`, write the tests, then run them in the foreground, and see them fail for the expected reason **before** writing any code they cover. A run that overlaps with writing the code does not count.

**Kit run rule**: Every scripted Kit run has an outer time limit, writes its results to a file, and ends with `os._exit`, because `post_quit` does not end Kit (see `research.md`, "Closing Kit"). After each run, confirm that no `kit` process is left.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to

## Path Conventions

- `EXT` means `omniverse/exts/highbay.replay`, and `CORE` means `omniverse/exts/highbay.replay/highbay/replay/core`.
- Test file names are unique across `tests/`, as the existing tests have no packages.
- `tests/conftest.py` stays the only `conftest.py`. A second one breaks `from conftest import ...`, which 25 existing test files use.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prove that the application can start from the repository, before anything depends on it

- [X] T001 Run the unchanged suite to establish a green start with `uv run pytest -q -rf --tb=short`, and record the result
- [X] T002 Change the version to `0.4.0` in `pyproject.toml` and `src/highbay_sim/__init__.py`, run `uv sync`, and confirm that `tests/integration/test_reference_results.py` still passes (SC-008)
- [X] T003 Create `omniverse/highbay.replay.app.kit` from the template's `source/apps/my_company.my_editor.kit`, with `telemetry.enableAnonymousData = false`, the title "Highbay Replay", and a dependency on `highbay.replay`; and create `EXT/config/extension.toml` with `python.module` set to `highbay.replay.extension`, plus empty `EXT/highbay/replay/__init__.py` and a minimal `EXT/highbay/replay/extension.py` that logs one line at startup. Then start it once from outside the template's build folder, with `kit.exe omniverse/highbay.replay.app.kit --ext-folder omniverse/exts`, and confirm the log line and "RTX ready". **This is the risk named in `research.md`, "Where the code lives"**: if dependencies do not resolve, try the template's `extscache` as a further `--ext-folder`, and then copying the file to `source/apps`. Record the outcome in `research.md`
- [X] T004 Create `omniverse/setup.ps1` per `contracts/application.md`: clone `kit-app-template` at commit `b8e9f2e`, stop with exit code 2 if `.omniverse_eula_accepted.txt` is missing, naming the terms and the command that shows the prompt (it never creates that file), replay `.vscode/replay_files/base_editor`, set `telemetry.enableAnonymousData = false` in the generated `source/apps/my_company.my_editor.kit` before building, build, and skip steps already done
- [X] T005 Create `omniverse/run-replay.ps1` per `contracts/application.md`, using the way of starting that T003 confirmed, and passing the run folder as the setting `/exts/highbay.replay/run_folder`
- [X] T006 [P] Add the `omniverse` marker, `-m "not omniverse"` in `addopts`, and `omniverse/exts/highbay.replay` as a pytest path, add `CORE` to mypy's files and ruff's sources in `pyproject.toml`, and make sure that importing `highbay.replay.core` needs no Kit. A `-m` on the command line replaces the default, so `-m omniverse` runs Kit tests, and any other `-m` should add `and not omniverse`, as the README must say
- [X] T007 [P] Add a helper in `tests/kit_runner.py`, not in a new `conftest.py`, for both `tests/omniverse_kit/` and `tests/performance/`, that finds Kit through `HIGHBAY_KIT_DIR` or the default folder, skips `omniverse` tests when it is missing, starts Kit with a test script under a time limit, reads the results file, and fails with the log's tail if no results appear

**Checkpoint**: The application starts from the repository with data collection off, and tests can start Kit or skip without it.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The state interface and the logic behind it, which every user story needs

**CRITICAL**: No user story work can begin until this phase is complete.

- [X] T008 [P] Write failing tests in `tests/omniverse/test_core_motion.py` for `axis_distance` and `movement_position`, with values worked out by hand in comments: acceleration, constant speed, braking, a short move with no constant speed, and arrival. These follow `src/highbay_sim/viewer/motion.js`
- [X] T009 [P] Write failing tests in `tests/omniverse/test_core_layout.py` for `create_layout`, following `src/highbay_sim/viewer/layout.js`: cell boxes, rack and aisle positions, bounds, and the instance number rule in `data-model.md`, "`(aisle-1, rack-1, bay-1, level-1)` in mixed-radix form"
- [X] T010 [P] Write failing tests in `tests/omniverse/test_core_playback.py`, following `src/highbay_sim/viewer/playback.js`, using an injected clock: speeds 1, 10, 60, 600, and 3,600, an initial speed of 60, staying within the run, stopping at the end of a final range, holding at the end of a growing range and continuing when it grows (`contracts/state-interface.md`), and restart
- [X] T011 [P] Write failing tests in `tests/omniverse/test_core_recording.py`, following `src/highbay_sim/viewer/replay-file.js`: a good file; a missing file; invalid JSON; `format_version` 999, with both versions named; and each required part missing or with the wrong structure. Each error is a `StateSourceError` naming the file and the problem
- [X] T012 [P] Write failing tests in `tests/omniverse/test_core_recorded_source.py` for `RecordedSource`, following `src/highbay_sim/viewer/replay-state.js` and `tests/viewer/test_replay_state.py`: each event kind, reservations, picks and sets at cells and aisle ends, `take_changes`, all contract operations in `contracts/state-interface.md`, and clamping of time. Include the rule from `data-model.md`, "Reaching a time by playing, or by moving forward or backward, gives the same state", on `samples/small-warehouse.yaml` with 200 random times, and a recording with no orders and no events, which shows its initial stock over the whole time span
- [X] T013 [P] Implement `CORE/state_source.py` per `contracts/state-interface.md`: the `StateSource` protocol, `StateSourceError`, `INTERFACE_VERSION = 1`, and data classes for the warehouse description and run state in `data-model.md`. It has no operation that writes
- [X] T014 [P] Implement `CORE/motion.py` (depends on T008)
- [X] T015 [P] Implement `CORE/layout.py` (depends on T009)
- [X] T016 [P] Implement `CORE/playback.py` (depends on T010)
- [X] T017 Implement `CORE/recording.py` (depends on T011, T013)
- [X] T018 Implement `CORE/recorded_source.py` (depends on T012, T013, T014, T017)
- [X] T019 Write `tests/viewer/test_core_parity.py` (SC-002), marked `viewer`: for a run in each simulation mode on `samples/small-warehouse.yaml` and `samples/daily-scenario.yaml`, take 100 sampled times including event times, call `stateAt` and `storedLoadUnits` from `replay-state.js` through the existing `modules` fixture, and compare with `RecordedSource`. Crane positions differ by no more than 1 cm, and every load unit's location and all figures match. Add a comparison of `layout.js` with `CORE/layout.py` on the same warehouse
- [X] T020 Write `tests/omniverse/test_core_independence.py`: no module in `CORE` imports `omni`, `carb`, `pxr`, `highbay_sim`, or anything outside the standard library; and no module in `src/highbay_sim` imports `highbay` (FR-011). Run `uv run --isolated --python 3.12 pytest tests/omniverse`, which downloads Python 3.12 on first use and leaves `.venv` alone, and confirm that it passes under Kit's Python version

**Checkpoint**: State logic exists, matches the browser viewer, and needs neither Kit nor a graphics card.

---

## Phase 3: User Story 1 - Replay a Recorded Run in Omniverse (Priority: P1) 🎯 MVP

**Goal**: Open a recording from either mode, and play it in RTX rendering.

**Independent Test**: `quickstart.md` S3, S4, S6, and S7.

### Tests for User Story 1

- [X] T021 [US1] Write failing tests in `tests/omniverse_kit/test_kit_scene.py`, marked `omniverse`: the prim paths and types in `data-model.md`, "Scene"; instance and prototype counts; stage up axis Y and 1 unit per meter; `invisibleIds` matching empty cells at time 0; a crane at the recorded position after moving to a time; after sampled moves, instances match `RecordedSource`; moving backward gives the same instance arrays as moving forward; a recording with no orders and no events builds its scene and plays to its end; and two builds of one recording give identical exported text (FR-016)
- [X] T022 [P] [US1] Write failing tests in `tests/omniverse_kit/test_kit_errors.py`, marked `omniverse`: a missing, damaged, and unsupported recording each shows a message naming the file and the problem, and no scene prims stay open (FR-014); with a run already open, an invalid folder leaves it open and unchanged, and a valid folder replaces it, paused at time 0 (`contracts/application.md`)

### Implementation for User Story 1

- [X] T023 [US1] Implement `EXT/highbay/replay/appearance.py`, the only module that decides how objects look: one function per object type in `contracts/application.md`, simple shapes sized as in `src/highbay_sim/viewer/appearance.js`, and the article and activity colors from "Color rules" in `data-model.md`
- [X] T024 [US1] Implement `EXT/highbay/replay/scene.py` (depends on T023): `build_scene(stage, description)` for the paths in `data-model.md`, and `update(state, changes)`, which batches crane changes in one `Sdf.ChangeBlock`, changes only changed cells, and rewrites all instances once after moving backward. A load unit on a crane is drawn by the crane's own carried load. Run T021, and make it pass
- [X] T025 [US1] Implement the first part of `EXT/highbay/replay/window.py` in `omni.ui`: Open, with its rule for a run already open, play and pause, restart, time slider, speed, default view, simulated time, and the error message. Controls and speeds follow `contracts/application.md`
- [X] T026 [US1] Implement `EXT/highbay/replay/extension.py`: `open_run_folder(path)` reads `/exts/highbay.replay/run_folder` or a chosen folder, creates a `RecordedSource`, and calls `open_source(source)`, per `contracts/state-interface.md`. `open_source` builds the scene, and on each update advances `Playback` and applies the state, depending only on the `StateSource` protocol. Show errors in the window and keep no partial scene. Add the default camera, which looks steeply along the aisles as in `src/highbay_sim/viewer/scene.js`. Run T022, and make it pass
- [X] T027 [US1] Run `quickstart.md` S3 and S6 by hand with `out/small` and `out/small-stepped`, including the stopwatch time for SC-001, free view movement and **Default view** for FR-015, and a screenshot of each for the review
- [X] T028 [US1] Run `quickstart.md` S4. **This is the risk named in `research.md`, "Closing Kit"**. If closing the window does not end the application within 30 seconds, find the cause and fix it, for example by disabling the responsible extension in `omniverse/highbay.replay.app.kit`. If that fails, the extension ends the process when its main window closes. Record the outcome in `research.md`
- [X] T029 [US1] Confirm that the frame rate has no effect on state: add to `tests/omniverse_kit/test_kit_scene.py` a run that plays one span of simulated time at two different limits on update rate, and compares final states (FR-005); and a run at 3,600× with a low update rate, so that many events fall in one frame, whose final instances and figures match `RecordedSource` at the same time

**Checkpoint**: A planner can open a run and play it. This is the MVP.

---

## Phase 4: User Story 2 - Understand What Is Happening (Priority: P2)

**Goal**: Show figures and details that connect the picture to the throughput results.

**Independent Test**: `quickstart.md` S5.

### Tests for User Story 2

- [X] T030 [P] [US2] Write failing tests in `tests/omniverse/test_core_picking.py`, following `src/highbay_sim/viewer/picking.js` and `tests/viewer/test_picking.py`: the first occupied cell along a ray seen through empty cells, the nearest cell with none occupied, and no result for a ray that misses all racks. Add a comparison with `picking.js` at sampled rays to `tests/viewer/test_core_parity.py`
- [X] T031 [US2] Write failing tests in `tests/omniverse/test_core_reported.py`, without Kit: for every warehouse and scenario pair in `tests/data/reference_results.json`, the state at `reported.first_backlog_peak_s` has a total backlog equal to `reported.backlog_orders.max_in_window` (SC-006). Also write failing tests in `tests/omniverse_kit/test_kit_panels.py`, marked `omniverse`: figures match `RecordedSource` at sampled times; occupancy has 6 decimal places; a crane's color changes at the recorded time; and after the jump to the highest backlog on `samples/replay/overloaded-warehouse.yaml`, playback is paused, time equals `reported.first_backlog_peak_s`, and the backlog shown equals `reported.backlog_orders.max_in_window` (SC-006)

### Implementation for User Story 2

- [X] T032 [US2] Implement `CORE/picking.py` (depends on T030)
- [X] T033 [US2] Extend `EXT/highbay/replay/window.py` with all figures, the run's identification, the legend, and the jump to the highest backlog, per `contracts/application.md`. Run T031, and make it pass
- [X] T034 [US2] First try getting a click and camera ray from the viewport in Kit 110, in a small script. **This is the risk named in `research.md`, "Selection"**. If it works, add selection to `EXT/highbay/replay/extension.py` using `CORE/picking.py`, with crane boxes tested first, and the same rules as `contracts/application.md`. If it does not, add the fallback from `research.md`: a list of cranes and entry fields for a location. Record the outcome in `research.md`
- [X] T035 [US2] Show selection details in `EXT/highbay/replay/window.py` through `StateSource.cell` and `StateSource.load`, including the order served and "initial stock" where it applies, with an outline at the selected object
- [X] T036 [US2] Run `quickstart.md` S5 by hand, comparing with the browser viewer for the same selection at the same time

**Checkpoint**: Stories 1 and 2 work, and figures match the reported values.

---

## Phase 5: User Story 3 - Prepare for Live Data and Detailed Models (Priority: P3)

**Goal**: Prove that a different source and a different look need no other change.

**Independent Test**: `quickstart.md` S8.

### Tests for User Story 3

- [X] T037 [US3] Write `tests/data/scripted_state_source.py` only from `contracts/state-interface.md`: a small warehouse with one crane moving and one load unit, with `can_move_backward` false, `range_is_final` false, a range whose end grows, and no `reported`
- [X] T038 [US3] Write tests in `tests/omniverse_kit/test_kit_state_source.py`, marked `omniverse`: the scripted source, connected through `open_source`, drives the scene, and playback holds at the end of its range and continues when it grows; the time slider, restart, and jump to the highest backlog are disabled; and a check of the source tree shows that `scene.py` and `window.py` import only the protocol from `core`, not `RecordedSource` (SC-007). Fix any place where display code assumed a recording, keeping the interface unchanged
- [X] T039 [US3] Write failing tests in `tests/omniverse_kit/test_kit_looks.py`, marked `omniverse`, with a small test `.usda` file in `tests/data/`: a replacement crane mast is referenced, while its position over time stays the same; and a missing file gives the simple shape and a warning naming the type

### Implementation for User Story 3

- [X] T040 [US3] Add the settings `/exts/highbay.replay/looks/<type>` to `EXT/highbay/replay/appearance.py`, with the fallback and warning in `contracts/application.md`. Run T039, and make it pass

**Checkpoint**: All user stories are complete.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Performance proof, documentation, and final validation

- [X] T041 Write `tests/performance/test_omniverse_performance.py`, marked `performance` and `omniverse`, with the whole warehouse in view at 1920×1080, the frame limiter and eco mode off, and a run playing at 600×: SC-003 on the small sample, SC-004 on the planning target from `tests/performance/write_planning_target.py`, and SC-005 at 20 random times on a one-day small sample. Replace the "Limits of this measurement" and "Not measured" notes in `research.md` with the results. If a target is missed, report it to the project owner rather than changing the target
- [X] T042 [P] Update `README.md`: the Omniverse replay, its graphics requirements, `setup.ps1`, license terms, data collection being off, `run-replay.ps1`, and that Kit tests run only with `-m omniverse`, plus a link to `specs/004-omniverse-run-replay/contracts/application.md`. Change the sentence that names Omniverse as a later feature. Add a screenshot in `docs/media/` from T027
- [X] T043 [P] Add a look-replacement section to `EXT/README.md`, and confirm that it is enough to do `quickstart.md` S8 by hand
- [X] T044 Run `quickstart.md` S1 with Kit's folder renamed, and confirm that `omniverse` tests are deselected by default and skipped with `-m omniverse`, and that all others pass, including reference hashes (SC-008)
- [X] T045 Run `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`, and all tests, including `uv run pytest -m omniverse`
- [ ] T046 Run `quickstart.md` S7 and S10, timing S10 on a fresh clone in a new folder (SC-009). Use a new Kit folder, and have the project owner confirm the license prompt there, as nobody else may accept it

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies. T003 comes first among the new files, since the way of starting the application decides T005 and T007
- **Foundational (Phase 2)**: Depends on Setup, and blocks all user stories
- **User Stories (Phases 3 to 5)**: Depend on Foundational
- **Polish (Phase 6)**: Depends on all user stories

### User Story Dependencies

- **User Story 1 (P1)**: Starts after Foundational, and needs no other story
- **User Story 2 (P2)**: Needs the scene and window from User Story 1
- **User Story 3 (P3)**: Needs the scene and window from User Story 1, and is independent of User Story 2. T038 covers the panel controls only if User Story 2 is done

### Within Each User Story

- Tests come first, and for `core/` they must be seen to fail before code is written
- Risk checks (T003, T028, T034) come before work that relies on them
- A story is complete at its checkpoint, before the next story starts

### Parallel Opportunities

- T006 and T007, after T003
- T008 to T012 together, and then T013 to T016 together
- T021 and T022, which use different files
- T042 and T043
- Only one Kit run at a time, as runs compete for the graphics card and would disturb measurements

---

## Parallel Example: Foundational Phase

```text
Task: "Write failing tests in tests/omniverse/test_core_motion.py"
Task: "Write failing tests in tests/omniverse/test_core_layout.py"
Task: "Write failing tests in tests/omniverse/test_core_playback.py"
Task: "Write failing tests in tests/omniverse/test_core_recording.py"
Task: "Write failing tests in tests/omniverse/test_core_recorded_source.py"
```

Then run them all to completion, and confirm that they fail, before starting T013.

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1, and settle how the application starts
2. Complete Phase 2, and prove parity with the browser viewer
3. Complete Phase 3
4. **STOP and VALIDATE**: Run `quickstart.md` S3, S4, S6, and S7

### Incremental Delivery

1. User Story 1: a run can be replayed in RTX
2. User Story 2: figures and selection explain what is seen
3. User Story 3: the state interface and looks are proven, ready for later features

---

## Notes

- Nothing in `src/highbay_sim` changes except its version number, so simulation results change only in the recorded version.
- Kit, its downloads, and its license acceptance stay outside the repository.
- Scripted Kit runs open windows on the project owner's desktop unless they use `--no-window`. Announce any visible run before starting it.
- Commit only when the project owner asks.
