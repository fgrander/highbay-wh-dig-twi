---

description: "Task list for PLC Virtual Commissioning"
---

# Tasks: PLC Virtual Commissioning

**Input**: Design documents from `specs/006-plc-virtual-commissioning/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/plc-interface.md](contracts/plc-interface.md), [contracts/cli.md](contracts/cli.md), [quickstart.md](quickstart.md)

**Tests**: Required. Principle V of the constitution and the plan call for test-first work: write each test, confirm that it fails, then make it pass.

**Organization**: Tasks are grouped by user story, so that each story can be tested on its own.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on unfinished tasks)
- **[Story]**: The user story that the task belongs to (US1 to US4)

---

## Phase 1: Setup

**Purpose**: The approval that the constitution requires, and the project's dependency.

**⚠️ GATE**: T001 needs the approval of the project owner. Without it, stop: do no later task. Running a Spec Kit command is not approval.

- [X] T001 After the project owner has approved it in words, apply the amendment drafted at the end of `specs/006-plc-virtual-commissioning/research.md` to `.specify/memory/constitution.md`: extend Principle II and replace the last sentence of the first paragraph of Principle IV as drafted, state the rationale, set the version to 1.1.0, and set Last Amended to the date of the change. Then set the Principle II and IV rows in `specs/006-plc-virtual-commissioning/plan.md` to "Pass, by amendment 1.1.0"
- [X] T002 Add the optional extra `plc = ["s7commplus==0.3.0"]` and the same exact pin in the `dev` group in `pyproject.toml`, update `uv.lock`. No mypy override is needed, as the library ships its types
- [X] T003 [P] Create `src/highbay_sim/plc/__init__.py` with only a docstring, so that importing the package never imports `s7commplus`

---

## Phase 2: Foundational

**Purpose**: The interface derived from the signal list, the link that everything reaches a PLC through, the identity check, and the in-memory PLC that the tests of all stories use.

**⚠️ CRITICAL**: No user story can begin until this phase is complete.

- [X] T004 [P] Write failing tests in `tests/unit/test_plc_interface.py`: every signal of `SIGNALS` belongs to exactly one of `model_tags` and `plc_tags`, by its direction (`order_handling_to_controller` and `plant_to_controller` to the model; `controller_to_order_handling` and `controller_to_plant` to the PLC); names have the form `HB_Interface.crane_1.horizontal_actual_m`; number maps to `LReal`, integer to `DInt`, and both boolean types to `Bool`; `crane_count` must be "at least 1"; the six header tags have the names and types of `contracts/plc-interface.md`, which the test reads from that file; aisle `a` is `crane_a`
- [X] T005 [P] Write failing tests in `tests/unit/test_plc_link.py`: the codec turns `LReal`, `DInt`, and `Bool` into bytes and back with no change, and raises `LinkError` on a value of the wrong type; `confirm_simulated` accepts `1;6ES7 SIM-01500-APLC;S4.1`, and refuses nothing, an empty string, a real CPU's string such as `1;6ES7 511-1AK02-0AB0;V2.9`, a string with `SIM` anywhere but at the start of the order number, and a string in another shape; `open_link` raises `LinkUnavailable` with the text `uv sync --extra plc` when `highbay_sim.plc.s7_link` or `s7commplus` cannot be imported
- [X] T006 Implement `PlcInterface` in `src/highbay_sim/plc/interface.py`, derived from `SIGNALS` and the warehouse's `layout.aisle_count`, so that T004 passes
- [X] T007 Implement in `src/highbay_sim/plc/link.py`, with no import of `s7commplus`: the `TagLink` protocol with `device_string`, `cpu_state`, `tag_types`, `read`, `write`, and `close` as in `data-model.md`; `LinkError` and `LinkUnavailable`; the value codec; `PlcConnection` with `host`, `tls_ca`, and `password`, whose text form never shows the password; `confirm_simulated`, which allows only an order number starting with `6ES7 SIM-`; and `open_link(connection)`, which imports `highbay_sim.plc.s7_link` only when called, so that T005 passes
- [X] T008 Create the in-memory PLC in `tests/data/memory_plc.py`: a `TagLink` holding all tags, with a Python copy of the control logic of `BuiltInController` plus the hold time of 3 cycles, whose scans run at their own rate against the model's cycles. It records each write request in order, and can be set to report any device string, be in STOP, lack or mistype a tag, have wrong start values, freeze its heartbeat, or fail on the Nth request

**Checkpoint**: The interface, the identity check, and the in-memory PLC exist. The real connection does not.

---

## Phase 3: User Story 1 - Prepare an Empty Simulated PLC (Priority: P1) 🎯 MVP

**Goal**: From a warehouse definition, generate the source files to import into TIA Portal.

**Independent Test**: Generate the files for a sample warehouse, and check that every signal appears for every crane, with the right type and direction. Compiling them is a manual step, which needs TIA Portal.

### Tests for User Story 1

- [X] T009 [P] [US1] Write failing tests in `tests/unit/test_plc_source.py`: for 1, 2, and 3 cranes, `HB_Types.udt` holds every signal with its PLC type, and `HB_Interface.db` holds `crane_1` to `crane_N` and the six header tags, with start values equal to the interface version, the signal list version, and the crane count; `HB_Control.scl` holds `HB_CraneControl` and `HB_Main`, with one call per crane; the hold time follows the cycle time (150 ms at 50 ms); the software version appears in a comment; two generations are byte-identical; no date, absolute address, or path appears
- [X] T010 [P] [US1] Write failing tests in `tests/integration/test_plc_cli.py` for `highbay-sim plc-source`: it writes the three files, refuses existing files without `--overwrite`, passes `--cycle-ms` on, and works with `s7commplus` blocked from importing

### Implementation for User Story 1

- [X] T011 [US1] Generate `HB_Types.udt` and the optimized `HB_Interface.db` in `src/highbay_sim/plc/source.py`, from `PlcInterface` and the cycle time
- [X] T012 [US1] Generate `HB_Control.scl` in `src/highbay_sim/plc/source.py`, so that T009 passes: `HB_CraneControl` follows the states and the at-position shortcuts of `BuiltInController`, with the tolerance `POSITION_TOLERANCE_M`, copies job data when `job_id` changes, holds each start true and then false for the hold time, judges status only after that, starts nothing new while `fault_code` is not 0, and never sets `fault_reset`; `HB_Main` counts `plc_heartbeat` and handles `reset_request` and `reset_done`
- [X] T013 [US1] Add the `plc-source` command to `src/highbay_sim/cli.py`, as in `contracts/cli.md`, so that T010 passes

**Checkpoint**: The source files can be generated and reviewed. Whether they compile stays open until the first import.

---

## Phase 4: User Story 2 - Run the Warehouse Under PLC Control (Priority: P2)

**Goal**: A time-stepped run with a PLC as the controller, through the existing `Controller` interface, with the usual reports.

**Independent Test**: A whole run through the in-memory PLC, with no Siemens software. This does not exercise the real connection. Until Phase 5 is done, `--plc-host` can only stop with the message that the connection is unavailable, so no real device can be reached.

### Tests for User Story 2

- [X] T014 [P] [US2] Write failing tests in `tests/unit/test_stepped.py`: when a controller raises `ControllerStopped`, `simulate_stepped` returns what was recorded, with the reason, the message, and the stopping cycle; the plant does not advance after the stop; `RunRecord.duration_s` is the simulated time at the stop, not the planned duration; orders that would arrive after the stop are not added; any other exception still raises `ControllerError`; a run with no stop has empty stop information
- [X] T015 [P] [US2] Write failing tests in `tests/unit/test_plc_controller.py` for the start of a run, using `MemoryPlc`: the steps run in the order of `contracts/plc-interface.md`; a PLC not in RUN, a heartbeat that does not change within 2 s, and no `reset_done` within 5 s each refuse the run; all differences in tags, types, and start values are named at once; after the identity check, the starting values of all model tags are written under `reset_request`, so that values from an earlier run are gone; a refusal closes the link and never reaches the exchange
- [X] T016 [P] [US2] Write failing tests in `tests/unit/test_plc_exchange.py`, with an injected clock and no real waiting: only changed tags are written after the first cycle; a changed `job_id` is written afterwards in a request of its own; no tag that belongs to the PLC is ever written; commands read reach `CraneSignals`; a cycle longer than the cycle time counts as an overrun, and no cycle is skipped; a failed read or write raises `ControllerStopped` with `connection_lost` and is never retried; a heartbeat unchanged for 2 s gives `plc_not_running`; SIGINT gives `interrupted` at the next scan; nothing is written after a stop
- [X] T017 [P] [US2] Write failing tests in `tests/integration/test_plc_run.py`, using `MemoryPlc` with scans not aligned with the model's cycles: a run of a sample warehouse finishes the same orders as the built-in controller, in a total time within 5%; a refused command gives the signal list's fault code; a connection lost mid-run writes outputs that name the cycle and reason, with metrics over the time actually simulated; `result.json` holds the `plc` section of `contracts/cli.md` with `"reproducible": false`, and the report states the same facts; the outputs hold neither the host nor the password
- [X] T018 [US2] Add failing tests to `tests/integration/test_plc_cli.py`, with `open_link` replaced by `MemoryPlc`: `--plc-host` needs `--time-stepped`, and cannot be used with `--controller`; a differing interface and a PLC not in RUN exit with `EXIT_INVALID_INPUT`, and write no outputs; a stopped run writes its outputs, then exits with `EXIT_FAILURE`; no option takes a password, and `HIGHBAY_PLC_PASSWORD` reaches `PlcConnection`; `--plc-tls-ca` reaches `PlcConnection`

### Implementation for User Story 2

- [X] T019 [US2] Define `ControllerStopped(reason, message)` in `src/highbay_sim/controller.py`
- [X] T020 [US2] In `src/highbay_sim/stepped.py`, catch `ControllerStopped` ahead of the general handler, and add an optional stop field to `SteppedRun`, so that T014 passes. All other paths must stay as they are
- [X] T021 [US2] Implement `PlcController.prepare` in `src/highbay_sim/plc/controller.py`, in the states `created`, `prepared`, and `refused` of `data-model.md`, with `confirm_simulated` as its first step, ahead of anything that can write, so that T015 passes
- [X] T022 [US2] Implement `PlcController.scan` and the cycle clock in `src/highbay_sim/plc/controller.py`, so that T016 passes. The clock and the wait are injected, with `time.monotonic` and `time.sleep` as defaults. Ctrl+C sets a flag through a SIGINT handler, which is restored at the close, because it can arrive outside `scan`
- [X] T023 [US2] Add `PlcRunStats` with `device`, `interface_version`, `stop_reason` (`finished`, `connection_lost`, `plc_not_running`, or `interrupted`), `stopped_at_cycle`, `cycles`, `overrun_cycles`, `slowest_exchange_ms`, `simulated_s`, and `real_s` in `src/highbay_sim/plc/controller.py`, keeping only running figures, so that a long run stores no growing history of exchange times
- [X] T024 [US2] Add the `plc` section and its report lines to `src/highbay_sim/outputs.py`, only for PLC runs, and set the stated duration in `RunInfo` to the simulated time at a stop. Output of runs without a PLC must stay byte-identical
- [X] T025 [US2] Add `--plc-host` and `--plc-tls-ca` to `run` in `src/highbay_sim/cli.py`, and read `HIGHBAY_PLC_PASSWORD`, so that T017 and T018 pass. The exit codes are those of `contracts/cli.md`, the controller name is recorded as `plc`, and a signal file that is being recorded is kept when a run stops early

**Checkpoint**: A whole run works against the in-memory PLC. The real connection is still not there.

---

## Phase 5: User Story 3 - Refuse Anything but a Simulated PLC (Priority: P3)

**Goal**: The real connection, which can be used only after the identity check. Do this before anything is tried on a real instance.

**Independent Test**: Devices that report themselves as anything else, in `MemoryPlc`, a stub client, and the library's in-memory server: none receives a write.

### Tests for User Story 3

- [X] T026 [P] [US3] Write failing tests in `tests/unit/test_plc_refusal.py`, one case per device string of T005, plus a link that raises when asked for its identity: `prepare` refuses, the write log of `MemoryPlc` is empty, the message names the device, and the link is closed; a parser check confirms that no option of `run` or `plc-measure` turns the check off (SC-003)
- [X] T027 [P] [US3] Write failing tests in `tests/unit/test_s7_link.py`, with a stub client: `device_string` returns the string of the session, and nothing when the library's private attribute is missing or fails; `write` keeps the given order, makes one call, and raises `LinkError` on any failed item, with no retry; `tag_types` gives nothing for a missing name; a missing password or certificate gives a message that says what is missing, and no message holds the password
- [X] T028 [P] [US3] Write failing tests in `tests/integration/test_s7_refusal.py`: against the in-memory server of `s7commplus`, on a free local port, connecting succeeds, `prepare` is refused because no simulated identity is confirmed, and the server's memory is unchanged, so that nothing was written

### Implementation for User Story 3

- [X] T029 [US3] Implement the adapter in `src/highbay_sim/plc/s7_link.py`, the only file that imports `s7commplus`, using `read_tags`, `write_tags`, `resolve_tag`, and `get_cpu_state`, and `extract_session_version_string` for the device string, with any failure there read as unknown, so that T027 and T028 pass
- [X] T030 [US3] Add a test to `tests/unit/test_plc_refusal.py` that fails if any file under `src/` other than `src/highbay_sim/plc/s7_link.py` imports `s7commplus`, or if any file under `src/` other than `src/highbay_sim/plc/controller.py` calls `write` on a link, so that `PlcController` stays the only writer

**Checkpoint**: `--plc-host` now reaches a real device, and only a confirmed simulated one receives a write.

---

## Phase 6: User Story 4 - Know What Cycle Time Is Possible (Priority: P3)

**Goal**: A measurement of exchange time and held cycle time for the warehouse's number of cranes.

**Independent Test**: Run it against `MemoryPlc` with an injected clock, and check the reported figures. They say nothing about a real instance, and the test does not claim that they do.

### Tests for User Story 4

- [X] T031 [P] [US4] Write failing tests in `tests/unit/test_plc_measure.py`, with an injected clock and given exchange times: median, 99th percentile, slowest, and overruns are right; the start steps run first, so that a refused device receives no write; no job starts; the device is named in the printed text
- [X] T032 [US4] Add failing tests to `tests/integration/test_plc_cli.py` for `highbay-sim plc-measure`, with `open_link` replaced by `MemoryPlc`: `--seconds` is 60 by default, a refusal exits with `EXIT_INVALID_INPUT`, and a missing extra gives the install message

### Implementation for User Story 4

- [X] T033 [US4] Implement the measurement in `src/highbay_sim/plc/measure.py`, using the start steps and the exchange of `PlcController`, so that T031 passes
- [X] T034 [US4] Add the `plc-measure` command to `src/highbay_sim/cli.py`, as in `contracts/cli.md`, so that T032 passes

**Checkpoint**: All stories work against the in-memory PLC.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Show that nothing else changed, document it, and hand over what only a real instance can show.

- [X] T035 [P] Write `tests/integration/test_no_plc_unchanged.py`: in a subprocess with `s7commplus` blocked from importing, `validate`, `run`, and `run --time-stepped` work, and `s7commplus` and `highbay_sim.plc.s7_link` are absent from `sys.modules`; a time-stepped run has no `plc` section, and its `SteppedRun` has empty stop information. Together with the existing tests in `tests/integration/test_reference_results.py` and `tests/verification/test_stepped_hand_calculated.py`, which must pass with no reference value changed, this covers FR-013 and SC-006
- [X] T036 [P] Add a section "PLC runs" to `README.md`, which says what works, what is unproven until a real instance has run, that only simulated PLCs are accepted, and that the generated program is not safety-rated
- [X] T037 Raise the version to 0.6.0 in `pyproject.toml` and `src/highbay_sim/__init__.py`, and update `uv.lock`
- [X] T038 Run `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, and `uv run mypy`, and fix what they find
- [X] T039 Carry out part A of `specs/006-plc-virtual-commissioning/quickstart.md`, and correct it where it differs
- [ ] T040 **Manual, for the user, once S7-PLCSIM Advanced and TIA Portal are installed.** Carry out parts B and C of `specs/006-plc-virtual-commissioning/quickstart.md`. Record in `specs/006-plc-virtual-commissioning/research.md` the device string seen, the measured exchange times, and the five open points of `plan.md`, and correct the generator and steps as needed. Only this can close the compile in User Story 1, SC-001, SC-002, and SC-004

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: T001 blocks everything, and needs the project owner.
- **Foundational (Phase 2)**: Depends on Setup, and blocks all stories.
- **User Story 1 (Phase 3)**: Depends on Foundational only.
- **User Story 2 (Phase 4)**: Depends on Foundational. It does not need US1, since the tests use `MemoryPlc`.
- **User Story 3 (Phase 5)**: Depends on `PlcController.prepare` of US2 (T021).
- **User Story 4 (Phase 6)**: Depends on the exchange of US2 (T021, T022). The real measurement also needs US3.
- **Polish (Phase 7)**: Depends on all the stories. T040 also needs US1 for the files, and the user's installation.

### Why US3 Has P3 and Still Comes Before Any Real Use

The identity check itself is in Phase 2 and is the first step of `prepare`, so no path around it is ever built. The real adapter arrives only in Phase 5. So during Phase 4 there is nothing that can reach a device, and from Phase 5 on, everything that can is behind the check.

### Within Each User Story

- Tests are written first, and must fail before the implementation.
- Interface and link before the controller, the controller before the outputs, the outputs before the command line.

### Parallel Opportunities

- T003 can run alongside T002.
- T004 and T005 can run together. T006 and T007 can too, once their tests fail.
- US1 can run alongside US2, except that T013 and T025 both change `src/highbay_sim/cli.py`, and T010 and T018 both change `tests/integration/test_plc_cli.py`.
- The tests marked [P] within a story can run together.
- T035 and T036 can run together.

---

## Parallel Example: User Story 2

```text
Task: "Failing tests for the early stop in tests/unit/test_stepped.py" (T014)
Task: "Failing tests for the start of a run in tests/unit/test_plc_controller.py" (T015)
Task: "Failing tests for the exchange in tests/unit/test_plc_exchange.py" (T016)
Task: "Failing tests for whole runs in tests/integration/test_plc_run.py" (T017)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. T001: get the approval, and apply the amendment.
2. Complete Phases 1 and 2.
3. Complete Phase 3, and review the generated files.
4. **Stop and validate**: once TIA Portal is there, import and compile them. This is the earliest moment at which a real Siemens tool checks anything.

### Incremental Delivery

1. US1: source files, with no connection.
2. US2: whole runs against the in-memory PLC.
3. US3: the real adapter, behind the check.
4. US4: the measurement.
5. T040: the first real run, which is expected to bring corrections.

---

## Notes

- All automated tests together do not show that the connection works on a real PLC, or that the generated program compiles. `MemoryPlc` is a Python copy of the logic, so it also does not show that the SCL behaves the same. Only T040 can.
- Never add an option, an environment variable, or a test hook to the product code that skips the identity check.
- Never write connection details or secrets to the repository, reports, or logs.
- Commit only when the user asks.
