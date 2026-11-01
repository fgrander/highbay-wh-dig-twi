# Implementation Plan: Headless Throughput Simulation

**Branch**: `001-headless-throughput-sim` | **Date**: 2026-11-01 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-headless-throughput-sim/spec.md`

## Summary

Build a command-line discrete-event simulation of one high-bay warehouse. The warehouse and scenario are defined in YAML files and validated in full before a run. Each aisle has one stacker crane with trapezoidal motion and configurable inbound and outbound transfer points at either aisle end. A run produces a Markdown report, a JSON result, and a per-order CSV, all byte-identical for identical inputs and software version. The core is a Python library with no user interface, so the later 3D view and live data can attach through defined interfaces. See [research.md](research.md) for the decisions behind this approach.

## Technical Context

**Language/Version**: Python 3.12 or newer, developed on 3.14, managed with uv

**Primary Dependencies**: pydantic (input validation), PyYAML (input parsing); the simulation engine uses only the standard library

**Storage**: Files only: YAML inputs and `report.md`, `result.json`, and `orders.csv` outputs

**Testing**: pytest, with ruff for linting and formatting and mypy for type checking

**Target Platform**: Windows 11 as the primary platform; no platform-specific code, so Linux and macOS are expected to work but are not verified in this feature

**Project Type**: Library with a command-line interface

**Performance Goals**: 20 aisles, 100,000 cells, 24 simulated hours at 1,000 orders per hour in under 60 seconds on a typical desktop computer (SC-004)

**Constraints**: Must run with no display (FR-008); no use of wall-clock time or unseeded randomness in the simulation (FR-009); no network access

**Scale/Scope**: One warehouse per run; about 24,000 orders and 100,000 cells at the planning target

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle or rule | How this plan complies | Pre-design | Post-design |
|---|---|---|---|
| I. Simulation core independent of visualization | The engine has no user interface dependency; consumers read a typed event stream ([simulation-api.md](contracts/simulation-api.md)) | PASS | PASS |
| II. Reproducible simulation | Event-driven simulated time, deterministic tie-breaking, seeded and separated random streams, no timestamps in outputs | PASS | PASS |
| III. Credible throughput results | Metrics have written definitions, results record input hashes and assumptions, and hand-calculated scenarios verify results ([results.md](contracts/results.md), [quickstart.md](quickstart.md)) | PASS | PASS |
| IV. Live data as a later, pluggable option | Orders enter through an `OrderSource` interface; no live source is built and nothing writes to external systems | PASS | PASS |
| V. Test-first simulation logic | Tasks must write failing tests first for kinematics, allocation, engine, and metrics | PASS | PASS |
| VI. Incremental delivery and simplicity | Single package, two runtime dependencies, small custom event loop; the interfaces added are those exempted by Principles I and IV | PASS | PASS |
| Technical constraints | Inputs are versionable YAML, SC-004 states measurable targets, stack is chosen here, and no external credentials exist | PASS | PASS |
| Development workflow | Spec Kit sequence followed on a feature branch; result-changing commits must be marked after the first release of results | PASS | PASS |

No violations. No deviations need to be justified.

## Project Structure

### Documentation (this feature)

```text
specs/001-headless-throughput-sim/
├── plan.md              # This file
├── research.md          # Technical decisions and rationale
├── data-model.md        # Entities, validation rules, state transitions
├── quickstart.md        # Validation scenarios
├── contracts/
│   ├── cli.md           # Command-line interface
│   ├── input-format.md  # Warehouse and scenario files
│   ├── results.md       # Output files and metric definitions
│   └── simulation-api.md # Library interfaces for later features
├── checklists/
│   └── requirements.md  # Specification quality checklist
└── tasks.md             # Created by /speckit-tasks
```

### Source Code (repository root)

```text
pyproject.toml
uv.lock
src/highbay_sim/
├── __init__.py          # Package version
├── cli.py               # validate and run commands
├── config.py            # Input models, loading, validation, content hashes
├── orders.py            # Order, OrderSource, generated and explicit sources
├── kinematics.py        # Crane travel time calculation
├── allocation.py        # Free cells, stock, storage location rules
├── events.py            # Simulation event types
├── engine.py            # Discrete-event loop and crane behavior
├── metrics.py           # Metric calculation and written definitions
└── outputs.py           # report.md, result.json, orders.csv

samples/
├── small-warehouse.yaml
├── daily-scenario.yaml
└── invalid/             # Validation test inputs with known errors

tests/
├── unit/                # Kinematics, allocation, orders, metrics, config
├── integration/         # CLI runs, output contracts, reproducibility
├── verification/        # Hand-calculated scenarios
└── performance/         # SC-004 benchmark
```

**Structure Decision**: A single Python package with a `src` layout. The later 3D view will be a separate consumer of this library, so no multi-project structure is needed yet.

## Complexity Tracking

No constitution violations to justify.
