---

description: "Task list for the time-stepped plant model"
---

# Tasks: Time-Stepped Plant Model

**Input**: Design documents from `specs/003-time-stepped-plant-model/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included. Constitution Principle V requires test-first development for simulation logic, and Principle III requires verification against independently known results.

**Test-first rule**: For each test task, write the tests, then run them in the foreground, and see them fail for the expected reason **before** writing any code they cover. A run that overlaps with writing the code does not count, as this feature's plan states.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: The safety net for event-based results, recorded before any code changes

- [X] T001 Run the unchanged suite to establish a green start with `uv run pytest -q -rf --tb=short`. If the intermittent failure seen once on `main` after merging feature 002 appears (one test of 457, name not recorded), record the test's name in `specs/003-time-stepped-plant-model/research.md`, and fix its cause before continuing
- [X] T002 Create `tests/data/reference_results.json` with the software version 0.2.0 code still unchanged: for each pair of `samples/small-warehouse.yaml` with `samples/daily-scenario.yaml`, `samples/replay/overloaded-warehouse.yaml` with `samples/replay/busy-scenario.yaml`, `samples/verification/v1-warehouse.yaml` with `v1-scenario.yaml` and `v3-scenario.yaml`, and `samples/verification/v2-warehouse.yaml` with `v2-scenario.yaml`, record the SHA-256 of `orders.csv`, `report.md`, `result.json`, and `replay.json`, with the software version's text replaced by a fixed placeholder before hashing
- [X] T003 Write `tests/integration/test_reference_results.py`, which repeats T002's procedure and compares with `tests/data/reference_results.json`, and confirm that it passes on the unchanged code (SC-009)
- [X] T004 Change the version to `0.3.0` in `pyproject.toml` and `src/highbay_sim/__init__.py`, run `uv sync`, and confirm that `tests/integration/test_reference_results.py` still passes

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared order rules, axis motion, and signal definitions that every user story needs

**CRITICAL**: No user story work can begin until this phase is complete.

- [X] T005 [P] Write failing tests in `tests/unit/test_kinematics.py` for a new `axis_position(start_m, target_m, speed_m_s, acceleration_m_s2, elapsed_s)`, with values worked out by hand in comments: acceleration, constant speed, and braking phases of the full profile; the short profile with no constant speed; both directions; zero distance; before the start; exactly the target at and after the end; and agreement with `axis_travel_time` at the end
- [X] T006 [P] Write failing tests in `tests/unit/test_signals.py`: `SIGNAL_LIST_VERSION` is 1; every signal in `contracts/signal-list.md`'s tables exists in the code with the same name, direction, type, and unit, and the reverse, by parsing that file; fault codes and names equal its table; initial values are 0 or false, and `job_id` and `job_done_id` are 0
- [X] T007 Implement `axis_position` in `src/highbay_sim/kinematics.py` (depends on T005)
- [X] T008 Implement `src/highbay_sim/signals.py` (depends on T006): `SIGNAL_LIST_VERSION`, a slotted `CraneSignals` data class with every signal, a table of signal definitions, and the fault codes as an `IntEnum`
- [X] T009 Write failing tests in `tests/unit/test_order_handling.py` for a new `OrderHandling` class, covering each rule in `data-model.md` under "Order handling": a cell on arrival; first-come, first-served per aisle; a storage order waiting and later assigned when a cell is released; an unfulfillable retrieval with `reason` `no_stock`; the lowest-time aisle end, with the left end winning a tie; final reasons `no_free_cell` and `run_ended`; and the order of emitted events
- [X] T010 Move the order rules from `src/highbay_sim/engine.py` to `OrderHandling` in `src/highbay_sim/order_handling.py`, and make the engine use it (depends on T009); change no behavior, and confirm that `tests/integration/test_reference_results.py` and `tests/unit/test_engine.py` still pass

**Checkpoint**: Event-based results are proven unchanged, and shared rules, axis motion, and signals exist.

---

## Phase 3: User Story 1 - Run a Warehouse Cycle by Cycle (Priority: P1) 🎯 MVP

**Goal**: A planner runs an existing warehouse and scenario in time-stepped mode, and receives the same kinds of results as from an event-based run.

**Independent Test**: Run a sample with `--time-stepped`, and confirm that all orders pass through the signal interface and a report is written (`quickstart.md` S1 and S2).

### Tests for User Story 1 ⚠️

> **NOTE: Write these tests FIRST, and ensure they FAIL before implementation**

- [X] T011 [P] [US1] Write failing tests in `tests/unit/test_plant.py`, using the V1 warehouse: start positions equal those of event-based runs; a rising edge starts an axis, while holding a true value does not start it again; positions at chosen cycles equal `axis_position`; an axis stops exactly at its target and never overshoots; `*_in_position` signals follow the movement; each axis ends on the first boundary at or after its exact end; a pick and a set take `pick_time_s` and `set_time_s`, rounded up to a boundary; `load_present` and cell contents change when handling ends; position to place within 1 mm for a cell and for each aisle end; a load set at an outbound end leaves the warehouse; a controller writing to status signals changes nothing, as the plant overwrites them; each load unit is in exactly one place throughout (FR-005)
- [X] T012 [P] [US1] Write failing tests in `tests/unit/test_controller.py` for the built-in controller, with signals set by hand and no plant: it stays idle with `job_id` 0; a new `job_id` starts both axes towards the source; it picks only once both axes are in position; it then moves to the destination and sets; it writes `job_done_id`; it holds no rising-edge signal true for longer than needed; it needs one false cycle before the next edge. Also test that `src/highbay_sim/controller.py` imports nothing from `highbay_sim.plant`, `highbay_sim.stepped`, or `highbay_sim.order_handling` (FR-012)
- [X] T013 [P] [US1] Write failing tests in `tests/unit/test_stepped.py`: the fixed order in a cycle from `data-model.md`; time is `cycle * cycle_ms / 1000`, with no accumulated error over 72,000 cycles; a job written in a cycle is seen by the controller in that cycle; an arrival between boundaries takes effect at the next one, keeping its exact `arrival_s`; events have the kinds and fields of event-based runs, with `end_s` and positions filled in; a movement of zero distance writes no activity; a movement outside a job writes no event; open orders at the end get the same reasons as in event-based runs; arrivals after the last cycle start but within the duration are processed; an empty scenario works; the system clock is never read
- [X] T014 [P] [US1] Write failing tests in `tests/integration/test_stepped_cli.py` for `contracts/cli.md` and `contracts/results.md`: a run with `--time-stepped` writes the three result files; `run.execution` holds `time_stepped`, the cycle time, `built-in`, a null hash, and version 1; `faults` is an empty list; `report.md` has "Execution" and "Faults" sections; metrics have the same names and definitions as event-based runs; `--cycle-ms` of 0, 1,001, and a non-whole number exit with code 2 and a message naming the allowed range before any simulation; `--cycle-ms` without `--time-stepped` exits with code 2; two runs in processes with different `PYTHONHASHSEED` are byte-identical; a run needs no display (SC-001, SC-002)

### Implementation for User Story 1

- [X] T015 [US1] Implement `Plant` in `src/highbay_sim/plant.py` (depends on T008, T011), with crane, axis, cell, and inbound state as in `data-model.md`, closed-form motion through `axis_position`, end cycles worked out when a movement starts, rising-edge detection, all status signals written in each cycle, and callbacks for a started movement, started handling, a finished pick, and a finished set; leave fault checks for T029
- [X] T016 [US1] Implement the `Controller` protocol and `BuiltInController` in `src/highbay_sim/controller.py` (depends on T008, T012) with the states in `data-model.md`, using only `highbay_sim.signals`
- [X] T017 [US1] Implement `simulate_stepped` in `src/highbay_sim/stepped.py` (depends on T010, T015, T016, T013), returning the existing `RunRecord`: the cycle sequence from `data-model.md`, jobs written from `OrderHandling`, the load unit offered at the chosen inbound end when a storage order starts, plant callbacks turned into events, and `Allocation` updated on a finished pick and set; emit no event from a callback when the crane has no current order
- [X] T018 [US1] Add the `execution` and `faults` output in `src/highbay_sim/outputs.py`, for time-stepped runs only, with the plant model's assumptions and the sources of deviation from `research.md` added to `assumptions` (FR-023), and the "Execution" and "Faults" report sections, following `contracts/results.md`; confirm that `tests/integration/test_reference_results.py` still passes
- [X] T019 [US1] Add `--time-stepped` and `--cycle-ms` to `run` in `src/highbay_sim/cli.py` (depends on T014, T017, T018), with the validation and exit codes in `contracts/cli.md`

**Checkpoint**: User Story 1 works. All tests from T011 to T014 pass, and `quickstart.md` S1 and S2 succeed.

---

## Phase 4: User Story 2 - Compare With the Event-Based Simulation (Priority: P2)

**Goal**: A planner runs both modes and sees how far their results deviate, and hand-calculated scenarios confirm the plant model.

**Independent Test**: Run verification scenarios and a sample in both modes, and compare them with the stated limits (`quickstart.md` S3).

### Tests for User Story 2 ⚠️

- [X] T020 [P] [US2] Write failing tests in `tests/unit/test_compare.py` for `contracts/cli.md`: every metric of both runs with absolute and relative deviation; a value of 0 in A shows only the absolute deviation; identical runs show 0; different warehouse or scenario hashes are refused, with a message naming the difference; each run's mode and cycle time are shown, with event-based results shown as such
- [X] T021 [P] [US2] Write tests in `tests/verification/test_stepped_hand_calculated.py` for the scenarios and hand-calculated values in `tests/verification/test_hand_calculated.py`: each order's completion time deviates by at most 2 cycles for each of its movement and handling steps, at 50 ms and at 10 ms (SC-003)
- [X] T022 [P] [US2] Write tests in `tests/verification/test_stepped_vs_event.py` for each pair of samples in `tests/data/reference_results.json`: total, storage, and retrieval throughput deviate by at most 1% or one completed order, whichever is larger, at 50 ms and at 5 ms (SC-004); record the measured deviations in a comment, and if the limit fails, find the cause rather than widen it
- [X] T023 [P] [US2] Add failing tests to `tests/integration/test_stepped_cli.py` for `compare`: exit codes 0 and 2, a directory or a file as an argument, a missing or damaged file, and no files written

### Implementation for User Story 2

- [X] T024 [US2] Implement `src/highbay_sim/compare.py` (depends on T020), reading both `result.json` files with no dependency on the simulation modules
- [X] T025 [US2] Add the `compare` command to `src/highbay_sim/cli.py` (depends on T023, T024)

**Checkpoint**: User Stories 1 and 2 work. `quickstart.md` S3 and S4 succeed.

---

## Phase 5: User Story 3 - Replace the Controller Through the Signal Interface (Priority: P3)

**Goal**: An automation engineer connects a different controller using only the signal list, and reads a record of signals and faults.

**Independent Test**: Drive the plant with a scripted test controller written only from the signal list, and confirm that a load unit is stored and retrieved (`quickstart.md` S5).

### Tests for User Story 3 ⚠️

- [X] T026 [P] [US3] Write failing tests in `tests/unit/test_plant_faults.py`, with one case for each code in `contracts/signal-list.md`, from `target_out_of_range` to `conflicting_commands`: the command has no effect; `fault_code` is set; the fault is recorded with its cycle, time, crane, code, name, and description; the count and locations of load units are unchanged; while the fault is active, other commands are ignored; a running movement finishes; a rising edge on `fault_reset` clears it; another crane carries on throughout (FR-006, SC-008)
- [X] T027 [P] [US3] Write failing tests in `tests/integration/test_controller_replacement.py`, and create `tests/data/scripted_controller.py` written only from `contracts/signal-list.md`, which is a fixed sequence, unlike the built-in state machine, and imports only `highbay_sim.signals`: it completes V1's storage and retrieval through `--controller`, with the load unit ending as expected (SC-007); `run.execution.controller` holds `scripted_controller.py:ScriptedController` and the file's hash; a missing file, a missing class, and a class with no `scan` method exit with code 2; a controller raising an error exits with code 1, naming the cycle, and writes no result files; a controller that sends an invalid command gets a fault in `result.json` and exit code 0; a controller that does nothing leaves orders as backlog; the plant module is not changed for any of these
- [X] T028 [P] [US3] Write failing tests in `tests/unit/test_signal_record.py` and add to `tests/integration/test_stepped_cli.py` for `contracts/results.md`: the first rows hold every signal's value at cycle 0; later rows hold changes only; order of cycle, crane, and signal list; true and false, and exact numbers; byte-identical files across runs; all other outputs identical with and without `--record-signals` (FR-019); an existing `signals.csv` needs `--overwrite`; an overwriting run without recording deletes it; `--record-signals` and `--controller` without `--time-stepped` exit with code 2

### Implementation for User Story 3

- [X] T029 [US3] Add the fault checks to `src/highbay_sim/plant.py` (depends on T015, T026), with the codes and behavior in `data-model.md` and `contracts/signal-list.md`, and make `BuiltInController` in `src/highbay_sim/controller.py` stop work on a crane with a fault, with no reset; carry recorded faults through `src/highbay_sim/stepped.py` to the outputs
- [X] T030 [US3] Add `load_controller` to `src/highbay_sim/controller.py` for `FILE.py:CLASS`, with the file's name and hash, and add `--controller` to `src/highbay_sim/cli.py` (depends on T027), checking it before any simulation; stop a run in `src/highbay_sim/stepped.py` when a controller raises an error, reporting the cycle
- [X] T031 [US3] Implement `src/highbay_sim/signal_record.py` (depends on T028), streaming to `signals.csv`, add `--record-signals` to `src/highbay_sim/cli.py`, and add `signals.csv` to the output files in `src/highbay_sim/outputs.py`, with the handling of existing files in `contracts/cli.md`

**Checkpoint**: User Stories 1, 2, and 3 work. `quickstart.md` S5 and S7 succeed.

---

## Phase 6: User Story 4 - Replay a Time-Stepped Run in 3D (Priority: P4)

**Goal**: A planner opens a time-stepped run in the existing 3D replay.

**Independent Test**: Write a replay from a time-stepped run, open it, and compare crane positions at chosen times with the plant's recorded positions (`quickstart.md` S6).

### Tests for User Story 4 ⚠️

- [X] T032 [US4] Write failing tests in `tests/viewer/test_stepped_replay.py`, using the existing browser fixtures in `tests/conftest.py`: `--time-stepped --replay` writes a file that the viewer opens with no error; end-of-run figures equal `result.json`; crane positions at chosen cycle boundaries deviate from the values in a `signals.csv` of the same run by at most 1 cm (SC-006); a chosen load unit is in the expected cell at a chosen time. In `tests/integration/test_stepped_cli.py`, also test that all other files are byte-identical with and without `--replay`

### Implementation for User Story 4

- [X] T033 [US4] Add `run.execution` to the replay in `src/highbay_sim/replay.py`, and allow `--replay` with `--time-stepped` in `src/highbay_sim/cli.py` (depends on T032), for time-stepped runs only; make no change to the viewer, or record why one is needed in `contracts/results.md`; confirm that `tests/integration/test_reference_results.py` still passes

**Checkpoint**: All user stories work. `quickstart.md` S6 succeeds.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Performance, documentation, and final validation

- [X] T034 [P] Write `tests/performance/test_stepped_performance.py` with the `performance` marker, using the planning-target warehouse from `tests/performance/test_benchmark.py`: one simulated hour at 1,000 orders per hour and 50 ms in under 60 seconds (SC-005); record the measured time and the machine in `specs/003-time-stepped-plant-model/research.md`
- [X] T035 [P] Update `README.md`: time-stepped runs and their options, `compare`, choosing a controller, the signal record, a link to `specs/003-time-stepped-plant-model/contracts/signal-list.md`, and a note that Omniverse and PLC connections are later features; replace the manual comparison steps only where `compare` does the same job
- [X] T036 [P] Check `tests/unit/test_signals.py` and the assumptions text against the final code, and update `specs/003-time-stepped-plant-model/data-model.md` and `research.md` wherever the implementation differs, including any deviation from the spec found while building
- [X] T037 Build in defects to check the tests: for each of the plant's motion end, rising-edge detection, status overwriting, a fault check, the cycle order, job completion, and signal recording, make one small temporary change, confirm that a test catches it, close any gap found, and restore the code
- [X] T038 Run `quickstart.md` S1 to S8, and record any scenario that cannot be run automatically and what the project owner must check
- [X] T039 Run `uv run pytest -q -rf --tb=short`, `uv run ruff check .`, `uv run ruff format --check .`, and `uv run mypy src`, and confirm that all pass; repeat the test suite once if T001 found no cause for the intermittent failure, and report any failure's test name

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies. T002 and T003 must come before any code change.
- **Foundational (Phase 2)**: Depends on Setup, and blocks all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational
- **User Story 2 (Phase 4)**: Depends on User Story 1, as it compares its results
- **User Story 3 (Phase 5)**: Depends on User Story 1, and not on User Story 2
- **User Story 4 (Phase 6)**: Depends on User Story 1. T032's position check also needs `--record-signals` from T031.
- **Polish (Phase 7)**: Depends on all user stories

### Within Each User Story

- Tests first, confirmed failing in a completed run, before any code they cover
- `signals.py` before `plant.py` and `controller.py`, and these before `stepped.py`
- `stepped.py` and `outputs.py` before `cli.py`

### Parallel Opportunities

- T005 and T006
- T011, T012, T013, and T014, then T015 and T016 after them
- T020, T021, T022, and T023
- T026, T027, and T028
- T034, T035, and T036
- User Stories 2 and 3 can run side by side after User Story 1, but both change `src/highbay_sim/cli.py`, so those tasks must not overlap

---

## Parallel Example: User Story 1

```text
Task: "Write failing tests in tests/unit/test_plant.py"
Task: "Write failing tests in tests/unit/test_controller.py"
Task: "Write failing tests in tests/unit/test_stepped.py"
Task: "Write failing tests in tests/integration/test_stepped_cli.py"
```

Then run them all to completion, and confirm that they fail, before starting T015.

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1, and record the reference results
2. Complete Phase 2
3. Complete Phase 3
4. **STOP and VALIDATE**: Run `quickstart.md` S1 and S2

### Incremental Delivery

1. User Story 1: runs cycle by cycle and writes results
2. User Story 2: credibility through hand calculations and comparison
3. User Story 3: the replaceable controller, faults, and signal record, which prepare the PLC connection
4. User Story 4: seeing a run in the existing viewer

---

## Notes

- Moving order rules (T010) is the only change to event-based code, and it is covered by T003.
- The event-based simulation must stay byte-identical except for the software version. Any other change must be named in the commit message, as the constitution requires.
- Commit only when the project owner asks.
