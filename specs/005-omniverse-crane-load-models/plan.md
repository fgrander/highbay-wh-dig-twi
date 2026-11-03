# Implementation Plan: Omniverse Crane and Load Models

**Branch**: `005-omniverse-crane-load-models` | **Date**: 2026-11-03 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/005-omniverse-crane-load-models/spec.md`

## Summary

Show a two-column stacker crane, fork sections that extend during recorded handling, and pairs of particle board and laminated sheet stacks in the Omniverse replay. Models are generated from a warehouse's dimensions when a run is opened, by standard library code that needs no Kit. A pure function turns a recorded handling step and a time into fork and pair positions. Pair definitions are a TOML file. The instancer keeps one instance per cell, with one prototype per pair, so its structure and cost stay close to feature 004's. The simulation, its results, the recording format, and the browser replay do not change.

## Technical Context

**Language/Version**: Python 3.12 in Kit, and core modules also under the project's Python 3.14, as in feature 004

**Primary Dependencies**: Omniverse Kit SDK 110.4.1 and OpenUSD 0.25.11, as in feature 004. No new dependencies: core modules use the standard library, including `tomllib`.

**Storage**: Reads `replay.json` and one TOML file. The scene is held in memory, and no files are written.

**Testing**: pytest, written test-first for core modules, without Kit. Scene, display, and selection are tested in Kit under the `omniverse` marker, with manual steps in [quickstart.md](quickstart.md) for what depends on a reviewer's judgment.

**Target Platform**: Windows 11 with an RTX 3080 class graphics card, for the Omniverse part only

**Project Type**: Extension of the existing desktop application extension

**Performance Goals**: SC-006 (30 frames per second on the small sample, 10 at 100,000 cells) and SC-007 (under 5 minutes to open at 100,000 cells). A prototype reached 39 frames per second with an array write in every frame, without racks and cranes ([research.md](research.md)).

**Constraints**: Results stay byte-identical except for the software version. Shown positions depend only on simulated time and recorded data. Nothing is written to the run folder or the repository. All dimensions are placeholders that can be changed.

**Scale/Scope**: Up to 20 aisles and 100,000 cells, with one crane per aisle and a few pair definitions

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle or rule | How this plan complies | Pre-design | Post-design |
|---|---|---|---|
| I. Simulation core independent of visualization | Only the extension changes. The existing test that the simulation imports nothing from it stays. | PASS | PASS |
| II. Reproducible simulation | No simulation code changes. Fork and pair positions are a pure function of simulated time and recorded data, and a built scene has no machine details. | PASS | PASS |
| III. Credible throughput results | No metric changes. The figures keep following the recording during handling. The documentation states that a pair is one article and one order, so throughput counts pairs (FR-018). | PASS | PASS |
| IV. Live data as a later, pluggable option | Handling details reach the display through one optional field of the state interface, with no way to write. A source without them still works. | PASS | PASS |
| V. Test-first simulation logic | Core modules are written test-first. Display code has tests in Kit where practical, and otherwise the manual steps in the quickstart. | PASS | PASS |
| VI. Incremental delivery and simplicity | Each story can be demonstrated on its own. Added complexity is justified below. | PASS | PASS |
| Technical constraints | Pair definitions and sizes are versionable data. Performance targets are stated, and no credentials are involved. | PASS | PASS |
| Development workflow | Spec Kit sequence on a feature branch. No change alters simulation results, and reference hashes check this. The branch builds on feature 004, which has to be merged first. | PASS | PASS |

No violations.

## Project Structure

### Documentation (this feature)

```text
specs/005-omniverse-crane-load-models/
├── plan.md              # This file
├── research.md          # Technical decisions, measurements, and open risks
├── data-model.md        # Handling steps, fork positions, types, pairs, and the scene
├── quickstart.md        # Validation scenarios and manual steps
├── contracts/
│   ├── state-interface.md  # The added field
│   └── application.md      # Settings, definitions file, display, and selection
├── checklists/
│   └── requirements.md  # Specification quality checklist
└── tasks.md             # Created by /speckit-tasks
```

### Source Code (repository root)

```text
omniverse/
├── run-replay.ps1           # Changed: -LoadDefinitions
├── highbay.replay.app.kit   # Changed: default settings
├── models/                  # Removed: generation moves into the extension
└── exts/highbay.replay/
    ├── README.md            # Changed: placeholder dimensions, definitions, and what a pair counts as
    ├── data/
    │   └── load_definitions.toml  # New: default types and pairs
    └── highbay/replay/
        ├── core/
        │   ├── state_source.py      # Changed: HandlingStep, CraneState.handling, version 2
        │   ├── recorded_source.py   # Changed: fills in handling
        │   ├── fork_motion.py       # New: fork and pair positions from a step and a time
        │   ├── crane_dimensions.py  # New: sizes and selection boxes of the crane
        │   ├── crane_model.py       # New: crane parts as USDA text, moved from models/
        │   ├── load_models.py       # New: stacks as USDA text
        │   ├── load_definitions.py  # New: reads and checks definitions, and gives warnings
        │   ├── layout.py            # Changed: rack member thickness
        │   ├── picking.py           # Changed: boxes come from a given crane shape
        │   └── display_text.py      # Changed: pair lines
        ├── appearance.py    # Changed: generated models, pair prototypes, and aisle lights
        ├── scene.py         # Changed: fork stages, carried pair, and fewer array writes
        ├── window.py        # Changed: warnings
        └── extension.py     # Changed: settings and definitions

tests/
├── omniverse/               # New tests: fork motion, dimensions, models, definitions, handling
├── omniverse_kit/           # New tests: detailed scene, and settings for simple models in old tests
└── performance/             # Changed: SC-006 and SC-007 with detailed models

pyproject.toml               # Changed: version 0.5.0
README.md                    # Changed: crane, pairs, and definitions
```

**Structure Decision**: Everything lives in the existing extension. Model generation moves into `core/` so that a run opened from the window can have any size of warehouse, and so that the generated text can be tested without Kit. `crane_model.py` and `crane_dimensions.py` are separate because selection needs the sizes but not the text.

## Implementation Order

This follows the story priorities, so that each step can be shown.

1. **User Story 1**: `crane_dimensions`, `crane_model`, generated cranes in the scene, selection boxes, aisle lights, and status colors. Loads remain single boxes, placed as today.
2. **User Story 2**: `handling` from recordings, `fork_motion`, moving fork stages, the carried pair's offset, and the hidden cell.
3. **User Story 3**: `load_definitions`, `load_models`, pair prototypes, details, and warnings.

## Complexity Tracking

| Addition | Why Needed | Simpler Alternative Rejected Because |
|----------|------------|--------------------------------------|
| Models generated as USDA text, then copied into the stage | FR-002 needs a crane for any warehouse, and a run can be opened from the window at any time | Files made before starting cannot follow a run chosen later. A reference to an anonymous layer leaves machine details in the scene. |
| A separate `simple` mode alongside detailed models | FR-017, and it keeps feature 004's tests and browser comparison valid | Removing the simple shapes would break FR-017, and all tests of them would have to be replaced |
| A hide of a stored pair that does not come from the recording | FR-007 asks to see the pair leave its cell during a handling step, while the recording moves it at the step's end | Showing the pair in both places, or moving it only at the event, contradicts the acceptance scenarios |

## Open Risks

- **Light in a full aisle**: The intensity is not known yet, and may not be enough ([research.md](research.md)). SC-004 decides, and a light on each crane is the fallback.
- **Status colors**: The strips may be too narrow for SC-004 and may have to become larger.
- **Sharing prototypes between instancers**: Each crane's carried pair is planned to use the prototypes of `/World/Loads`, which is not measured yet. If Kit does not render this, each crane gets its own group of prototypes, or the carried pairs are placed by one instancer of their own.
- **Performance**: The prototype had no racks or cranes. Only the performance tests with the full scene can prove SC-006.
- **Stepped recordings**: The check that events end their handling steps was run only on an event-driven recording. A task checks it for stepped ones, and `RecordedSource` reports a recording where it fails.
- **Real dimensions**: These are still missing, and may change forks, stacks, and whether the sample's stacks fit.
