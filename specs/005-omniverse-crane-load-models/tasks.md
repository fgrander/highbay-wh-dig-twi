---

description: "Task list for the Omniverse crane and load models"
---

# Tasks: Omniverse Crane and Load Models

**Input**: Design documents from `specs/005-omniverse-crane-load-models/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included. Constitution Principle V requires automated tests for visualization where practical, and documented manual steps otherwise. The logic in `core/` is written test-first.

**Test-first rule**: For each test task on `core/`, write the tests, then run them in the foreground, and see them fail for the expected reason **before** writing any code they cover.

**Kit run rule**: Every scripted Kit run has an outer time limit, writes its results to a file, and ends with `os._exit`, as `post_quit` does not end Kit. After each run, confirm that no `kit` process is left. Announce a visible Kit window to the project owner before opening one.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to

## Path Conventions

- `EXT` means `omniverse/exts/highbay.replay`, and `CORE` means `omniverse/exts/highbay.replay/highbay/replay/core`.
- Test file names are unique across `tests/`, as the existing tests have no packages.
- `tests/conftest.py` stays the only `conftest.py`.
- Core modules use only the standard library, and syntax valid under both Python 3.12 and 3.14.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: A green start, and old tests protected from the change of default

- [X] T001 Run the unchanged suite with `uv run pytest -q -rf --tb=short` and `uv run pytest -m omniverse -q`, and record the results
- [X] T002 Change the version to `0.5.0` in `pyproject.toml` and `src/highbay_sim/__init__.py`, run `uv sync`, and confirm that `tests/integration/test_reference_results.py` still passes (SC-008)
- [X] T003 Add a parameter `models`, default `"simple"`, to `run_kit_script` in `tests/kit_runner.py`, which passes `--/exts/highbay.replay/models=<value>`, so that the tests of feature 004 keep checking the simple scene (FR-017). The setting has no effect until T016
- [X] T004 [P] Add a test in `tests/omniverse/test_handling_in_recordings.py` that runs `samples/small-warehouse.yaml` in both event and `--time-stepped` modes, and checks in each that every `load_picked` and `load_set` event falls on the end of its crane's latest `handling` activity, and that each one at a cell has the crane's target at x = (bay − 0.5) × cell length and y = (level − 1) × cell height. If it fails for stepped mode, stop and update `research.md` and `data-model.md` before continuing. This closes the open risk "Stepped recordings" in `plan.md`

**Checkpoint**: All tests pass, and the assumptions about recordings hold for both modes.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The crane's sizes in one place, which the model and selection both depend on

**CRITICAL**: No user story work can begin until this phase is complete.

- [X] T005 [P] Move `RACK_MEMBER_THICKNESS_M` from `EXT/highbay/replay/appearance.py` to `CORE/layout.py`, and add `pair_base_height()` to `Layout`, returning (1 − `LOAD_SIZE_SHARE`) / 2 × cell height, with a test in `tests/omniverse/test_core_layout.py`
- [X] T006 Write failing tests in `tests/omniverse/test_crane_dimensions.py` per `data-model.md`, "CraneDimensions": column and section positions, reach from aisle and cell width, fork bottom and top; that the forks fit between beam and load at the sample's dimensions, and at a low cell height where they cannot, which raises no error and gives forks 2 cm thick; and that `crane_boxes` returns the parts named, with forks and load at given offsets. At the sample's dimensions, no box of the forks or a load overlaps a rack beam or the crane's floor tie at the lowest level, and a load as long as a cell does not overlap the carriage's end frames or the columns (User Story 1, scenario 5). A ray through the opening between the columns hits no box
- [X] T007 Implement `CORE/crane_dimensions.py`, with the placeholder values from `omniverse/models/build_crane_model.py`, until T006 passes

**Checkpoint**: Crane sizes exist, and can be used and tested without Kit.

---

## Phase 3: User Story 1 - See a Realistic Crane at Work (Priority: P1) 🎯 MVP

**Goal**: A two-column crane moving along its aisle, which can be seen in a full aisle and selected on any visible part.

**Independent Test**: `quickstart.md` S2 and S3.

### Tests for User Story 1

- [X] T008 [P] [US1] Write failing tests in `tests/omniverse/test_crane_model.py`: the text for a mast and a carriage is valid USDA by a check of its balanced structure and required prims; it holds both columns, the top beam, travel gear, and both sections with `Base`, `Middle`, and `Top`; identical inputs give identical text; and the part sizes follow `crane_dimensions` for two different warehouses (FR-001, FR-002, FR-009). Parsing with USD itself belongs in T010
- [X] T009 [P] [US1] Write failing tests in `tests/omniverse/test_core_picking.py` for `pick_crane` with a given crane shape: a hit on a column, the top beam, the carriage, and the forks selects the crane, a ray through the opening does not, and calling it with no shape gives feature 004's result. The existing tests stay unchanged
- [X] T010 [US1] Write a test in `tests/omniverse_kit/test_kit_crane.py` with `tests/omniverse_kit/crane_script.py`, using `models="detailed"`, that opens a run and checks: each crane's generated prims exist and materials are bound; no reference to an anonymous layer is in the root layer, and two builds of the `/World` subtree are identical; crane parts are within 1 cm of the recorded position at 100 sampled times, in both modes (SC-001); each of the boxes from `crane_boxes` matches the bounds of its part in the stage, within 1 cm (FR-005); clicks as rays at 20 sampled points select the crane (SC-003); the status strips take each activity's color (FR-004); the selection outline of a crane surrounds its load space per `data-model.md`, "Selection outline" (FR-005); and a light exists per aisle (FR-014)

### Implementation for User Story 1

- [X] T011 [US1] Move `omniverse/models/build_crane_model.py` to `CORE/crane_model.py` with `git mv`, take its sizes from `crane_dimensions`, return text instead of writing files, remove its command line part, and make T008 pass. Remove the folder `omniverse/models/`
- [X] T012 [US1] Add a parameter for the crane's shape to `pick_crane` and `select_at` in `CORE/picking.py`, until T009 passes
- [X] T013 [US1] In `EXT/highbay/replay/appearance.py`, add a function that imports USDA text into an anonymous layer and copies it to a path in the stage's root layer with `Sdf.CopySpec`, per `research.md`, "Models are generated while opening a run"; and use it in `create_crane` when models are detailed and no file replaces the part. Keep the top prim's `primvars:displayColor`, so that parts with no material show the activity. A file given for a look still wins, with a warning that selection keeps using the generated dimensions
- [X] T014 [US1] In `appearance.py`, add `create_aisle_lights`, with one rectangular light per aisle per `data-model.md`, "Scene", and call it from `EXT/highbay/replay/scene.py` when models are detailed
- [X] T015 [US1] Use `crane_dimensions`' boxes for selection with detailed models in `EXT/highbay/replay/extension.py`, and raise the outline of a selected crane or carried load per `data-model.md`, "Selection outline"
- [X] T016 [US1] Read the setting `/exts/highbay.replay/models` in `EXT/highbay/replay/extension.py`, with default `detailed`, per `contracts/application.md`, and pass it to the scene. Confirm that all tests of feature 004 pass with `simple`
- [X] T017 [US1] Generate a recording with a full aisle, or use `out/overloaded`, and capture sample images along an aisle for each of the four activities without a window. Set the light's intensity and, if needed, widen the status strips or color larger parts, until the crane and its activity can be told apart (SC-004). If the aisle light is not enough, use the fallback in `research.md`, "Aisle light". Record the decision and values in `research.md`, and store the images in `specs/005-omniverse-crane-load-models/images/`
- [X] T018 [US1] Send the images and a short video to the project owner for review, since the first design was rejected, and wait for the answer before starting Phase 4

**Checkpoint**: A planner sees and selects a realistic crane. This is the MVP.

---

## Phase 4: User Story 2 - See the Forks Handle Loads (Priority: P2)

**Goal**: Fork sections extend during recorded handling, and the load moves with them.

**Independent Test**: `quickstart.md` S4.

### Tests for User Story 2

- [X] T019 [P] [US2] Write failing tests in `tests/omniverse/test_core_recorded_source.py` per `contracts/state-interface.md`: `handling` is None outside a step, and gives kind, location, start, and end inside one, for picks and sets at cells and aisle ends; it is the same reached forward or backward; `carrying`, cells, and all figures are unchanged by it; and a handling activity with no matching event at its end gives None, and raises no error, while an event with no matching activity, as in the existing test recording, still opens
- [X] T020 [P] [US2] Write failing tests in `tests/omniverse/test_fork_motion.py` per `data-model.md`, "ForkPose", with values worked out by hand: rest at the start and end; constant rates; fully extended from 40% to 60%; the sign for each rack; load and hidden cell for pick and set in each phase; rest with a location of None or no step; a zero-length step does not divide by zero; and one rack per aisle
- [X] T021 [US2] Write a test in `tests/omniverse_kit/test_kit_forks.py` with `tests/omniverse_kit/forks_script.py`, using `models="detailed"`: for one pick and one set per rack, stages of both sections are at the expected positions at start, 20%, 50%, 80%, and end (SC-002); a stored instance is hidden per the pose; the same time reached forward and backward gives the same positions and arrays (FR-008); figures do not change before the event (FR-016); `Section1` and `Section2` are separately movable prims (FR-009); a scripted source with no handling leaves the forks at rest; and a carriage look with no stages does not stop a run

### Implementation for User Story 2

- [X] T022 [US2] Add `HandlingStep` and `CraneState.handling` to `CORE/state_source.py`, and change `INTERFACE_VERSION` to 2, along with its check in `tests/omniverse/test_core_recorded_source.py`. Confirm that `tests/data/scripted_state_source.py` still works unchanged
- [X] T023 [US2] Fill in `handling` in `CORE/recorded_source.py`, by adding kind and location to the latest handling activity of a crane while indexing events, until T019 passes
- [X] T024 [US2] Implement `CORE/fork_motion.py` until T020 passes
- [X] T025 [US2] Change `create_crane` in `appearance.py` so that with detailed models, `CarriedLoad` is a group or instancer that can be moved along z. Test sharing prototypes between instancers first in a short Kit script, take the fallback in `plan.md`, "Open Risks", if it does not render, and record the result in `research.md` and `data-model.md`
- [X] T026 [US2] In `EXT/highbay/replay/scene.py`, write the fork stages and the carried load's offset as attribute specs per `data-model.md`, "Scene"; show the carried load during a pick, from the cell's load; and skip stages that do not exist. Do nothing of this with simple models
- [X] T027 [US2] In `scene.py`, combine source-based hidden cells with those from poses per `data-model.md`, "Stored instances", and write the arrays only when their content changed, until T021 passes. Confirm that the test of a backward move, where all cells are redrawn, still passes
- [X] T028 [US2] Pass forks' and load's positions to the boxes used for selection in `extension.py`, so that clicking on extended forks selects the crane, with a case added to T021
- [X] T029 [US2] Send a short video of a pick and a set to the project owner

**Checkpoint**: Handling can be followed and is the same from any direction.

---

## Phase 5: User Story 3 - See What Is Stored (Priority: P3)

**Goal**: Each load shows its unit or its two parts, defined per article in data.

**Independent Test**: `quickstart.md` S5 and S6.

### Changes from the clarification of 2026-11-03

- [X] T048 [US3] Rename `pair` to `load` in the code and tests of Phases 2 to 4, such as `pair_offset_m`, `pair_on_crane`, and `pair_base_height`, as a load is not always two units. Behavior stays the same, and all tests still pass
- [X] T049 [US3] Test first in `tests/omniverse/test_crane_dimensions.py`: section positions per `data-model.md`, "CraneDimensions", at cell lengths of 3.2 m and 5.8 m, and that each section's tines stay within the outer 1.5 m of a 5.6 m load. Then change `CORE/crane_dimensions.py`
- [X] T050 [P] [US3] Create `samples/replay/real-size-warehouse.yaml` with cells 5.8 m long, 1.5 m high, and 2.3 m wide, and `samples/replay/real-size-scenario.yaml` with the articles `paper-5610`, `board-5600`, `board-2100-3500`, and `board-3000-2600`, marking in comments which values are placeholders. Existing samples and reference results do not change

### Tests for User Story 3

- [X] T030 [P] [US3] Write failing tests in `tests/omniverse/test_load_definitions.py` per `data-model.md`, "LoadUnitType", "LoadDefinition", and "Warnings": a good file; a missing file; invalid TOML; each rule for each field; an unknown type in a load; relative paths from the file's folder; an article of the run with no definition; a load that does not fit its cell, with article and size named; a split that does not add up to 5.6 m, a part below 1.5 m, and a split of a type that cannot be split, with article and lengths named; positions of one unit and of two parts with an off-center cut; a definition for an article not in the run gives no warning; and each warning occurs once
- [X] T031 [P] [US3] Write failing tests in `tests/omniverse/test_load_models.py`: a board stack has `count` boxes and the right height, at any length; a paper pallet has one base board below its block of sheets, the right total height, and two subsets that together cover each face of the block once; the origin is on the floor at the center; and identical inputs give identical text
- [X] T032 [P] [US3] Write failing tests in `tests/omniverse/test_core_display_text.py` for the `Load` lines in `contracts/application.md`, "Displayed information", for a stored whole unit, a stored split stack, a carried load, and an undefined article (FR-015)
- [X] T033 [US3] Write a test in `tests/omniverse_kit/test_kit_loads.py` with `tests/omniverse_kit/loads_script.py`, using `models="detailed"`, that opens a run with a definitions file: one prototype per distinct load definition plus one per article color; each stored and carried load uses its article's prototype; each part of a split stack has its length, and lies above its section (User Story 3, scenarios 1 and 2); the instance count equals the cell count; a missing file, an unknown type, an undefined article, and a bad split open, and the warnings are shown in the window (FR-013); and a `file` type is used as given

### Implementation for User Story 3

- [X] T034 [US3] Implement `CORE/load_definitions.py` with `tomllib` until T030 passes
- [X] T035 [US3] Implement `CORE/load_models.py` per `research.md`, "Load unit geometry", until T031 passes
- [X] T036 [P] [US3] Create `EXT/data/load_definitions.toml`, with the types and loads from `contracts/application.md` for the articles of T050, plus smaller types and loads for `oak-panel-18mm` (split) and `paper-a4-80g` (one pallet) that fit the existing samples' cells, with comments saying which values are real and which are placeholders (FR-012)
- [X] T037 [US3] In `appearance.py`, create load prototypes as `Unit1`, and `Unit2` for a split, under `/World/Loads/Load_<i>`, one per distinct load definition, plus one box per article color. Give a simple box to a unit whose type is unknown or cannot be loaded
- [X] T038 [US3] In `scene.py`, use these prototypes for stored and carried loads, through a map from article to prototype, keeping one instance per cell, and use a load's own size for its selection box
- [X] T039 [US3] In `extension.py`, read `/exts/highbay.replay/load_definitions` with its default in the extension's folder, each time a run is opened. A `load_unit` look gives a warning with detailed models. Add `-LoadDefinitions` to `omniverse/run-replay.ps1`
- [X] T040 [US3] Add the `Load` lines to `CORE/display_text.py` until T032 passes, and add a warnings section to `EXT/highbay/replay/window.py`, hidden when empty, until T033 passes
- [X] T041 [US3] Capture default and close views of cells of all articles from T050, with a whole unit and two different cuts, have the project owner review them (SC-005), and store them in `specs/005-omniverse-crane-load-models/images/`

**Checkpoint**: All user stories are complete.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Performance proof, documentation, and final validation

- [ ] T042 Pass `models="detailed"` in `tests/performance/test_omniverse_performance.py`, and run it with the small sample and the warehouse with 100,000 cells (SC-006, SC-007). Record results and limits in `research.md`. If a target is missed, report the numbers to the project owner before changing any target
- [ ] T043 [P] Time the steps of `quickstart.md` S5 from changing a stack's size to seeing it (SC-009), and record this in `research.md`
- [ ] T044 [P] Update `EXT/README.md`: all placeholder dimensions and where to change them, the definitions file, the rules for files, and that a carriage needs `Section1` and `Section2` with `Middle` and `Top` to move (FR-018)
- [ ] T045 [P] Update `README.md` with the crane, loads, the settings, and a new image in `docs/media/`. State that a load is one article and one order to the simulation, so that throughput figures count loads, and that this is why result files keep saying that multi-load handling is not modeled (FR-018)
- [ ] T046 Run all checks: `uv run pytest`, `uv run pytest -m omniverse`, the core tests under Kit's Python 3.12, `ruff`, and `mypy`, and confirm that reference results are unchanged (SC-008) and that no `kit` process is left
- [ ] T047 Go through `quickstart.md` S2 to S7 with the project owner, in a visible window, as buttons, the slider, and the mouse camera have not been tested by hand in this project yet

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies. Feature 004's code is already on this branch, although not merged.
- **Foundational (Phase 2)**: Depends on Setup, and blocks all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational. T018 waits for the project owner.
- **User Story 2 (Phase 4)**: Depends on User Story 1's crane, because the forks are parts of it.
- **User Story 3 (Phase 5)**: Depends on Foundational, and could start after User Story 1. T038 uses the carried load of T025 and T026, so User Story 2 goes first in this plan.
- **Polish (Phase 6)**: Depends on all stories.

### Within Each User Story

- Core tests fail before their code exists, as the test-first rule requires.
- Kit tests are written with their story's tests, and pass at the end of its implementation.
- Core modules come before scene code, and scene code before the window.

### Parallel Opportunities

- T004 and T005 touch separate files.
- T008 and T009, T019 and T020, and T030, T031, and T032 are separate test files.
- T036 is independent of code, and T043, T044, and T045 of each other.
- Tasks that change `appearance.py`, `scene.py`, or `extension.py` run in order. Only one Kit run at a time should be used for measurements.

---

## Parallel Example: User Story 3 Tests

```text
T030 tests/omniverse/test_load_definitions.py
T031 tests/omniverse/test_load_models.py
T032 tests/omniverse/test_core_display_text.py
```

---

## Implementation Strategy

### MVP First

1. Finish Phases 1 and 2.
2. Finish Phase 3, and stop at T018. The crane's design was rejected once, so the project owner sees it before more is built on it.

### Incremental Delivery

1. The crane (User Story 1), shown with images and a video.
2. The forks (User Story 2), shown with a video.
3. Loads and stacks (User Story 3), reviewed with images.
4. Performance, documentation, and a test by hand.

### Before Merging

Feature 004 has to be merged first. Its open items are T046 of that feature, the project owner's test by hand, and the decision on the intermittent viewer test.
