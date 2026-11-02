# Implementation Plan: Time-Stepped Plant Model

**Branch**: `003-time-stepped-plant-model` | **Date**: 2026-11-02 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/003-time-stepped-plant-model/spec.md`

## Summary

Add a second way to run a warehouse: `highbay-sim run --time-stepped` advances a plant model in fixed cycles. A controller reads and sets a vendor-neutral list of signals in each cycle, using per-axis positioning. Order handling stays in the simulation and gives the controller transport orders. Runs produce the same `RunRecord` as event-based runs, so metrics, result files, and the 3D replay are reused. The order rules move from `engine.py` to a shared module, and fixed reference hashes prove that event-based results do not change. See [research.md](research.md) for the decisions behind this approach.

## Technical Context

**Language/Version**: Python 3.12 or newer, as in the existing project

**Primary Dependencies**: No new dependencies. Existing: pydantic and PyYAML at run time, and pytest, ruff, mypy, and Playwright for development.

**Storage**: Files only: the existing outputs, plus `signals.csv` when recording is switched on

**Testing**: pytest, written test-first for the plant model, signal handling, built-in controller, order handling, and comparison. Hand-calculated scenarios and fixed reference hashes check the results. The existing Playwright setup checks a time-stepped run in the viewer.

**Target Platform**: Windows 11 with no graphics requirement, as this feature is headless

**Project Type**: Existing library and command-line interface

**Performance Goals**: At 20 aisles, 100,000 cells, 1,000 orders per hour, and the default cycle time of 50 ms: one simulated hour in under 60 seconds (SC-005). A prototype loop with always-busy cranes needed about 1.2 seconds for this in plain Python, without order handling, so the target appears reachable with room to spare.

**Constraints**: Event-based results stay byte-identical except for the software version (SC-009). Simulated time never depends on the system clock. There are no external connections.

**Scale/Scope**: 72,000 cycles per simulated hour at the default cycle time, with one crane per aisle and about 24 signals per crane

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle or rule | How this plan complies | Pre-design | Post-design |
|---|---|---|---|
| I. Simulation core independent of visualization | Runs are fully headless. The viewer still only reads a saved file. | PASS | PASS |
| II. Reproducible simulation | Time is a whole number of cycles of a whole number of milliseconds, so no rounding errors accumulate. The run waits for the controller in each cycle and never uses the system clock. Tests compare repeated runs byte for byte. | PASS | PASS |
| III. Credible throughput results | Metrics use the same code and definitions as event-based runs. Hand-calculated scenarios and a comparison with event-based results check them, and every known source of deviation is documented ([research.md](research.md)). | PASS | PASS |
| IV. Live data as a later, pluggable option | No connection to any external system is built. The signal list prepares a later connection, and that feature will have to amend this principle, because signals are written towards a controller. | PASS | PASS |
| V. Test-first simulation logic | Each logic module has its tests written and confirmed failing before its code exists. Test-first runs must finish before any code is written, as a run in parallel with coding does not count. | PASS | PASS |
| VI. Incremental delivery and simplicity | Each story can be demonstrated. Added complexity is justified below. | PASS | PASS |
| Technical constraints | Performance targets are stated. Inputs stay data, and no credentials are involved. | PASS | PASS |
| Development workflow | Spec Kit sequence on a feature branch. Moving order rules out of `engine.py` must not alter simulation results, and reference hashes enforce this. | PASS | PASS |

No violations.

## Project Structure

### Documentation (this feature)

```text
specs/003-time-stepped-plant-model/
├── plan.md              # This file
├── research.md          # Technical decisions and rationale
├── data-model.md        # Plant, cycle, job, and fault behavior
├── quickstart.md        # Validation scenarios
├── contracts/
│   ├── signal-list.md   # The versioned signal list
│   ├── cli.md           # New and changed commands
│   └── results.md       # Added output fields and signals.csv
├── checklists/
│   └── requirements.md  # Specification quality checklist
└── tasks.md             # Created by /speckit-tasks
```

### Source Code (repository root)

```text
src/highbay_sim/
├── cli.py               # Changed: run --time-stepped and its options, new compare command
├── engine.py            # Changed: uses order_handling.py; behavior unchanged
├── kinematics.py        # Changed: axis position at a time
├── outputs.py           # Changed: execution details and faults, for time-stepped runs only
├── replay.py            # Changed: execution details, for time-stepped runs only
├── order_handling.py    # New: order rules shared by both modes
├── signals.py           # New: signal definitions and the signal list version
├── plant.py             # New: the plant model
├── controller.py        # New: controller interface, built-in controller, and loading a controller
├── stepped.py           # New: the cycle loop and building the RunRecord
├── signal_record.py     # New: writes signals.csv
└── compare.py           # New: compares two result files

tests/
├── unit/                # New: signals, plant, controller, order handling, compare
├── integration/         # New: CLI, reference hashes, replacing the controller
├── verification/        # New: hand-calculated scenarios and comparison with event-based runs
├── viewer/              # New: a time-stepped run in the 3D replay
├── performance/         # New: SC-005
└── data/                # New: scripted test controller and reference hashes
```

**Structure Decision**: The new modules sit beside the event-based engine in the existing package. The controller module imports nothing from the plant module, and a test enforces this, so a later PLC connection can take the controller's place.

## Complexity Tracking

| Addition | Why Needed | Simpler Alternative Rejected Because |
|----------|------------|--------------------------------------|
| A second simulation mode next to the event-based engine | A PLC works cycle by cycle, which an event schedule that plans whole movements ahead cannot serve. The project owner chose this design. | Replacing the engine would give up fast, verified runs and the reference for SC-004 |
| A shared module for order rules | Both modes must apply the same rules (FR-013), and two copies could drift apart | Duplication needs no change to `engine.py`, but it leaves nothing to keep the rules equal |
| Loading a controller from a file | FR-016 needs a choice of controller with no change to the software | Passing a controller only in test code would leave planners no way to choose one |
| Job handshake signals | FR-011 keeps order handling out of the controller, so jobs must pass through the interface | Direct function calls would not exist on a real PLC, so the interface would not prepare its connection |
