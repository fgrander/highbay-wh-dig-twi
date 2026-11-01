---

description: "Task list for the headless throughput simulation"
---

# Tasks: Headless Throughput Simulation

**Input**: Design documents from `specs/001-headless-throughput-sim/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included. Constitution Principle V requires simulation logic and metric calculations to be developed test-first, and Principle III requires verification against independently known results.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- All paths are relative to the repository root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [ ] T001 Create `pyproject.toml` for package `highbay-sim` with `requires-python = ">=3.12"`, runtime dependencies `pydantic` and `PyYAML`, dev dependencies `pytest`, `ruff`, and `mypy`, script entry `highbay-sim = "highbay_sim.cli:main"`, a `src` layout, and ruff, mypy, and pytest configuration; create `src/highbay_sim/__init__.py` defining `__version__ = "0.1.0"`
- [ ] T002 Pin Python 3.14 in `.python-version` and generate `uv.lock` by running `uv sync`; do not use or modify the local Anaconda installation
- [ ] T003 [P] Create `.gitignore` covering `.venv/`, `out/`, `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, and `.ruff_cache/`
- [ ] T004 [P] Create `tests/conftest.py` with helpers `minimal_warehouse_dict()` and `minimal_scenario_dict()` that return valid inputs in the form defined by `specs/001-headless-throughput-sim/contracts/input-format.md`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Input handling, motion calculation, event types, and order sources needed by every user story

**CRITICAL**: No user story work can begin until this phase is complete. Write each test task first and confirm that it fails before its implementation task.

- [ ] T005 [P] Write failing tests in `tests/unit/test_kinematics.py` for the formula in `research.md`: `d/v + v/a` when `d >= v²/a`, otherwise `2·sqrt(d/a)`; zero distance takes 0 s; the two branches agree at `d = v²/a`; a movement takes the longer of its two axes; and `d=10, v=2, a=1` gives 7 s while `d=3, v=1, a=1` gives 4 s
- [ ] T006 [P] Write failing tests in `tests/unit/test_config.py` for every validation rule in T009, including: all problems in a file reported together with their field paths in the `<file>: <field path>: <problem>` format of `contracts/cli.md`; unknown fields rejected; and SHA-256 hashes unchanged by CRLF line endings or YAML key order, but changed by any value change
- [ ] T007 [P] Write failing tests in `tests/unit/test_orders.py`: `ExplicitOrders` sorts by time and keeps file order for equal times; `GeneratedOrders` yields only `arrival_s < duration_s` in non-decreasing order, gives the same sequence for the same seed and a different one for another seed, has a mean rate near `orders_per_hour` over a long run, respects `storage_share` and `article_weights`, and yields nothing at `orders_per_hour: 0`
- [ ] T008 [P] Create immutable (frozen) event types in `src/highbay_sim/events.py` with `time_s`, `sequence`, `kind`, and related IDs, for the kinds `order_arrived`, `order_waiting_for_cell`, `order_queued`, `order_unfulfillable`, `order_started`, `activity_started`, `load_picked`, `load_set`, and `order_completed`, and activities `moving_empty`, `moving_loaded`, and `handling`
- [ ] T009 Implement `src/highbay_sim/config.py` (depends on T006): pydantic models and YAML loading for both files in `contracts/input-format.md`, plus cross-field checks and a SHA-256 hash of the parsed content in canonical JSON. Enforce from `data-model.md`: `name` "Not empty"; `aisle_count` "Integer ≥ 1"; `racks_per_aisle` "1 or 2", default 2; `bays_per_rack`, `levels_per_rack` "Integers ≥ 1"; `cell` height, length, and width "Each > 0"; crane `horizontal`, `vertical` speed and acceleration "Each > 0"; `pick_time_s`, `set_time_s` "≥ 0"; `storage_rule` `nearest_free` or `random_free`; `seed` "Integer ≥ 0"; `duration_s` "> 0"; `warmup_s` "≥ 0 and < `duration_s`"; exactly one of `generated` or `orders`; `orders_per_hour` "≥ 0"; `storage_share` "0 to 1"; `article_weights` "non-negative, with a positive total"; order `time_s` "≥ 0 and < `duration_s`"; order `type` `storage` or `retrieval`; each aisle has "at least one inbound and one outbound point" after overrides; "An end lists each role at most once"; "Overrides refer only to aisles that exist"; stock "location exists and appears only once"; and `schema_version: 1`
- [ ] T010 [P] Implement `src/highbay_sim/kinematics.py` (depends on T005): axis travel time and the two-axis movement time
- [ ] T011 Implement `src/highbay_sim/orders.py` (depends on T007): `OrderRequest`, the `OrderSource` protocol from `contracts/simulation-api.md`, `ExplicitOrders`, and `GeneratedOrders` using Poisson arrivals and a `random.Random` seeded from a SHA-256 hash of the run seed and the stream name `orders`

**Checkpoint**: Foundation ready. All tests from T005 to T007 pass.

---

## Phase 3: User Story 1 - Run a Throughput Simulation (Priority: P1) 🎯 MVP

**Goal**: A planner runs one warehouse and a seeded scenario with no graphical interface and receives a report of all FR-012 metrics.

**Independent Test**: Run `samples/small-warehouse.yaml` with `samples/daily-scenario.yaml` with no display available; confirm a complete report, identical results on repetition, and rejection of invalid input (`quickstart.md` Scenarios 1, 2, 4, and 6).

### Tests for User Story 1 ⚠️

> **NOTE: Write these tests FIRST, and ensure they FAIL before implementation**

- [ ] T012 [P] [US1] Write failing tests in `tests/unit/test_allocation.py`: positions `(bay - 0.5) × cell length` and `(level - 1) × cell height`; the cell states in `data-model.md`; `nearest_free` picks the shortest travel time from an inbound point of the cell's aisle across all aisles, with ties in location order; `random_free` is reproducible, uses the stream `storage`, and considers all aisles; retrieval reserves the oldest stored, unreserved load unit of the article across all aisles; a reserved cell is unavailable to other orders
- [ ] T013 [P] [US1] Write failing tests in `tests/unit/test_engine.py`: the storage and retrieval cycle steps in `data-model.md`; each crane starts at its first inbound point, left before right; a crane stays at its last position between orders; first-come, first-served per crane; FR-001b point selection with left winning ties; a retrieval with no stock is immediately `unfulfillable` with reason `no_stock` and the run continues; stock becomes available only after set-down; a storage order with no free cell waits and receives a cell when one is released at pick-up; open orders at the end are `unfinished`; a scenario with no orders completes; the same inputs give the same events; results do not depend on `on_event`; and `simulate` still succeeds when file access, network access, and the system clock are patched to raise errors
- [ ] T014 [P] [US1] Write failing tests in `tests/unit/test_metrics.py` for each definition in `contracts/results.md`: window limits; throughput per hour in total and by type; mean, median (odd and even counts), nearest-rank 95th percentile, and maximum; activities clipped to the window; utilization shares summing to 1; backlog at the end and maximum; occupancy counting load units physically present; outcomes over the whole run; statistics are `null` with no data, while throughput is 0
- [ ] T015 [P] [US1] Write failing tests in `tests/integration/test_cli.py` for `contracts/cli.md`: `validate` and `run` success, exit codes 0, 1, and 2, `--version`, refusal to replace existing outputs without `--overwrite`, and a generated `report.md` and `result.json` containing every FR-012 metric and its definition and unit
- [ ] T016 [P] [US1] Write failing tests in `tests/integration/test_reproducibility.py`: 10 runs of the same inputs and seed give byte-identical `result.json` and `report.md`, including runs with busy background processes (SC-002); a different seed changes the order sequence and the recorded seed; and a run succeeds in a subprocess with `DISPLAY` removed and with no graphical module imported (FR-008)
- [ ] T017 [P] [US1] Write failing tests in `tests/integration/test_invalid_inputs.py`: every case in `samples/invalid/` exits with code 2, starts no simulation, and reports each expected field path (SC-006)

### Implementation for User Story 1

- [ ] T018 [P] [US1] Create `samples/small-warehouse.yaml` and `samples/daily-scenario.yaml` from `contracts/input-format.md`, with enough initial stock for retrievals and a comment stating that values are illustrative and not real equipment data
- [ ] T019 [P] [US1] Create `samples/invalid/` with one warehouse or scenario file per error, covering: no outbound point, no inbound point, zero aisle count, negative cell dimension, zero crane speed, duplicate stock, stock at a location that does not exist, override for an aisle that does not exist, unknown field, warm-up not shorter than duration; plus a file with several errors, and `samples/invalid/expected.yaml` listing each file's expected field paths
- [ ] T020 [US1] Implement `src/highbay_sim/allocation.py` (depends on T012, T010, T009): cell states, stock per article in stored-time order, `nearest_free` using a priority queue of precomputed travel times, and `random_free` using an indexable list with swap-removal
- [ ] T021 [US1] Implement `simulate` and crane behavior in `src/highbay_sim/engine.py` (depends on T013, T020, T011, T008): a discrete-event loop ordered by simulated time and sequence number, cell assignment at arrival, cycles and transfer point selection as in `data-model.md`, and the `RunRecord` and `on_event` behavior in `contracts/simulation-api.md`
- [ ] T022 [US1] Implement `calculate_metrics` and the written metric definitions in `src/highbay_sim/metrics.py` (depends on T014, T021), calculating only from the run's events and initial state
- [ ] T023 [US1] Implement `report.md` sections 2 to 6 and `result.json` in `src/highbay_sim/outputs.py` (depends on T022) as in `contracts/results.md`, with stable metric names, 3-decimal time formatting, no timestamps or machine details, and the seed in the `run` block
- [ ] T024 [US1] Implement `validate`, `run`, and `--version` in `src/highbay_sim/cli.py` (depends on T009, T023), with the output formats and exit codes in `contracts/cli.md`

**Checkpoint**: User Story 1 is fully functional. All tests from T012 to T017 pass, and `quickstart.md` Scenarios 1, 2, 4, and 6 succeed.

---

## Phase 4: User Story 2 - Verify and Trace Results (Priority: P2)

**Goal**: A planner can check what each number means, which inputs produced it, and that it matches hand-calculated results.

**Independent Test**: Run the verification scenarios and compare results to the calculated values, then confirm the inputs and each order can be traced from the output files (`quickstart.md` Scenario 3).

### Tests for User Story 2 ⚠️

> **NOTE: Write these tests FIRST, and ensure they FAIL before implementation**

- [ ] T025 [P] [US2] Write tests in `tests/verification/test_hand_calculated.py` that check results within 0.1% (SC-003) and show the calculation in comments, for: **V1** as defined in `quickstart.md` Scenario 3; **V2**, the V1 warehouse with inbound and outbound points at both ends and the free cell at bay 2, level 2, giving 5 s movements, storage completion at 25 s, and retrieval completion at 55 s, both via the left end; **V3**, V1 with `warmup_s: 20`, giving a 3,580 s window, throughput of `2 × 3600 / 3580` per hour, moving loaded 7/3580, handling 27/3580, idle 3546/3580, and waiting statistics from the retrieval order only
- [ ] T026 [P] [US2] Write failing tests in `tests/integration/test_traceability.py`: `result.json` and `report.md` contain the software version, seed, measurement window, and warehouse and scenario names and SHA-256 hashes; a hash matches an independent calculation from the input; the report contains the modeling assumptions; `orders.csv` has the exact header in `contracts/results.md`, one row per order, and correct `location`, `transfer_point`, `outcome`, and `reason` values

### Implementation for User Story 2

- [ ] T027 [P] [US2] Create the V1, V2, and V3 warehouse and scenario files in `samples/verification/`
- [ ] T028 [US2] Complete the `run` block of `result.json`, add `report.md` sections 1 and 7, and write `orders.csv` in `src/highbay_sim/outputs.py` (depends on T026), with the assumptions list from `spec.md` and `research.md` in both `result.json` and `report.md` (FR-014, FR-015, FR-016)
- [ ] T029 [US2] Correct any difference that T025 reveals in `src/highbay_sim/engine.py` or `src/highbay_sim/metrics.py` by fixing the cause, not the expected values, unless the hand calculation itself is shown to be wrong and that correction is documented in the test

**Checkpoint**: User Stories 1 and 2 both work. `quickstart.md` Scenario 3 succeeds.

---

## Phase 5: User Story 3 - Compare Warehouse Variants (Priority: P3)

**Goal**: A planner changes the warehouse design in data only and compares results for the same scenario.

**Independent Test**: Run the same scenario against variants that differ only in data, and compare their machine-readable results (`quickstart.md` Scenario 5).

### Tests for User Story 3 ⚠️

> **NOTE: Write these tests FIRST. Failures here show a gap in earlier stories that must be fixed at its cause.**

- [ ] T030 [P] [US3] Write tests in `tests/integration/test_variants.py` using the files from T031: every variant runs with no software change (SC-005); all `result.json` files have the same metric names and units; generated order times, types, and articles in `orders.csv` are identical across variants with the same seed; the higher-speed variant has no longer crane movement for orders with the same assignment; each aisle-count variant reports one crane per aisle; and transfer point variants use the configured points

### Implementation for User Story 3

- [ ] T031 [P] [US3] Create `samples/variants/` with copies of `samples/small-warehouse.yaml` that each change one thing: higher crane speed, different `aisle_count`, different cell dimensions and counts, `random_free` storage rule, and transfer points at both aisle ends
- [ ] T032 [US3] Create `README.md` with a section on comparing variants: which fields to change, keeping one scenario and seed, and which `result.json` fields to compare

**Checkpoint**: All user stories are independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T033 [P] Write `tests/performance/test_benchmark.py`, building a warehouse programmatically with 20 aisles and 100,000 cells, and asserting that 24 simulated hours at 1,000 orders per hour complete in under 60 seconds (SC-004)
- [ ] T034 [P] Update FR-001 in `specs/001-headless-throughput-sim/spec.md` to state that cell length and height determine crane travel distances, and that cell width is validated and recorded but does not affect travel, as decided in `research.md`
- [ ] T035 Extend `README.md` with installation via `uv sync`, usage of `validate` and `run`, input and output file references, and a statement that sample values are illustrative
- [ ] T036 Run `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src`, and `uv run pytest`, and fix every problem reported
- [ ] T037 Run every scenario in `specs/001-headless-throughput-sim/quickstart.md` and record any difference from the expected results

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies
- **Foundational (Phase 2)**: Depends on Setup; blocks all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational
- **User Story 2 (Phase 4)**: Depends on User Story 1, because it verifies and extends its outputs
- **User Story 3 (Phase 5)**: Depends on User Story 1; T030 also compares `orders.csv`, so it depends on T028 from User Story 2
- **Polish (Phase 6)**: Depends on all stories; T033 needs only User Story 1

### Within Each User Story

- Tests are written first and must fail before implementation
- Order within User Story 1: allocation (T020) → engine (T021) → metrics (T022) → outputs (T023) → CLI (T024)
- Task T025 uses results from an already-working engine, so it may pass at once; a pass still counts as verification only if the expected values were calculated independently

### Parallel Opportunities

- Setup: T003, T004
- Foundational: T005, T006, T007, T008 together; then T010 alongside T009 and T011
- User Story 1: T012 to T017 together; T018 and T019 together
- User Story 2: T025, T026, T027 together
- User Story 3: T030, T031 together
- Polish: T033, T034 together

---

## Parallel Example: User Story 1

```text
Task: "Write failing tests in tests/unit/test_allocation.py"
Task: "Write failing tests in tests/unit/test_engine.py"
Task: "Write failing tests in tests/unit/test_metrics.py"
Task: "Write failing tests in tests/integration/test_cli.py"
Task: "Write failing tests in tests/integration/test_reproducibility.py"
Task: "Write failing tests in tests/integration/test_invalid_inputs.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Run `quickstart.md` Scenarios 1, 2, 4, and 6

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. User Story 1 → working simulation and report (MVP)
3. User Story 2 → results verified and traceable
4. User Story 3 → variants confirmed as comparable
5. Polish → performance confirmed and documentation complete

---

## Notes

- [P] tasks use different files and have no dependencies on incomplete tasks
- Do not build a 3D view, live data connection, or anything else listed as out of scope in `spec.md`
- Commit after each task or logical group, and mark commits that change simulation results (constitution, Development Workflow)
- Stop at any checkpoint to validate a story independently
