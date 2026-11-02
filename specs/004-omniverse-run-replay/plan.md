# Implementation Plan: Omniverse Run Replay

**Branch**: `004-omniverse-run-replay` | **Date**: 2026-11-02 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/004-omniverse-run-replay/spec.md`

## Summary

Replay an existing `replay.json` in an NVIDIA Omniverse Kit application with RTX rendering. A new Kit extension in the repository generates the warehouse as an OpenUSD scene with simple shapes, and it gets all run state through one state interface. The first source behind that interface reads a recording, and a later feature can add a live source. The logic behind the interface has no Kit dependency, so the project's normal tests cover it and compare it with the browser viewer. The simulation does not change, and it never imports the extension.

## Technical Context

**Language/Version**: Python 3.12 for the extension, which is the version inside Kit. The extension's logic also runs under the project's Python 3.14 for tests, so it is limited to syntax that both versions support.

**Primary Dependencies**: NVIDIA Omniverse Kit SDK 110.4.1, installed outside the repository from `kit-app-template` at a fixed commit, including OpenUSD 0.25.11 and `omni.ui`. The extension's logic uses only the Python standard library. The simulation package has no new dependencies.

**Storage**: Reads `replay.json` only. The scene is held in memory, and no files are written.

**Testing**: pytest, written test-first for the logic modules. Playwright compares the logic with the browser viewer's state. Scene and display code is tested in Kit, under a new `omniverse` marker. These tests run only on request with `-m omniverse`, and are skipped when Kit is not installed, with documented manual steps for what cannot be automated.

**Target Platform**: Windows 11 with an RTX 3080 class graphics card, for the Omniverse part only. The simulation and browser replay keep running without it.

**Project Type**: Existing library and command-line interface, plus a separate desktop application extension

**Performance Goals**: SC-003 (30 frames per second on the small sample), SC-004 (10 frames per second at 100,000 cells), and SC-005 (under 1 second to move to any time). A prototype reached 40 frames per second or more at 100,000 instances with changes in every frame, but with only part of the warehouse in view ([research.md](research.md)).

**Constraints**: Results stay byte-identical except for the software version. The extension is read-only, and state depends only on simulated time and recorded data. Kit downloads and its license acceptance stay outside the repository.

**Scale/Scope**: Up to 20 aisles, 100,000 cells, and one instance for each cell, with one crane per aisle

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle or rule | How this plan complies | Pre-design | Post-design |
|---|---|---|---|
| I. Simulation core independent of visualization | The extension only reads recorded data. The simulation imports nothing from it, and a test enforces this. Tests without Kit prove that the simulation works on its own. | PASS | PASS |
| II. Reproducible simulation | No simulation code changes. Displayed state is a function of simulated time and recorded data, and it does not use the frame rate or the system clock. During playback, the system clock only decides how fast simulated time advances, as in the browser viewer. | PASS | PASS |
| III. Credible throughput results | Figures shown are computed by the same rules as the browser viewer, or read from `reported`. A test compares them at sampled times. No new metric is added. | PASS | PASS |
| IV. Live data as a later, pluggable option | All state enters through the state interface in [contracts/state-interface.md](contracts/state-interface.md). No live source is built, and the interface has no way to write. | PASS | PASS |
| V. Test-first simulation logic | Logic modules are written test-first. Display code has tests in Kit where practical and otherwise documented manual steps in [quickstart.md](quickstart.md). | PASS | PASS |
| VI. Incremental delivery and simplicity | Each story can be demonstrated. Added complexity is justified below. | PASS | PASS |
| Technical constraints | Performance targets are stated. Layouts stay data, and no credentials are involved. | PASS | PASS |
| Development workflow | Spec Kit sequence on a feature branch. No change alters simulation results, and existing reference hashes check this. | PASS | PASS |

No violations.

## Project Structure

### Documentation (this feature)

```text
specs/004-omniverse-run-replay/
├── plan.md              # This file
├── research.md          # Technical decisions, measurements, and open risks
├── data-model.md        # Run state, scene, and instance rules
├── quickstart.md        # Validation scenarios and manual steps
├── contracts/
│   ├── state-interface.md  # The interface between state sources and the display
│   └── application.md      # Starting the application, controls, looks, and errors
├── checklists/
│   └── requirements.md  # Specification quality checklist
└── tasks.md             # Created by /speckit-tasks
```

### Source Code (repository root)

```text
omniverse/
├── setup.ps1                # New: installs Kit from the fixed template commit
├── run-replay.ps1           # New: opens a run folder in the application
├── highbay.replay.app.kit       # New: the application definition, with data collection off
└── exts/highbay.replay/
    ├── README.md            # New: how to replace a look
    ├── config/extension.toml
    └── highbay/replay/
        ├── core/            # New: standard library only, no Kit imports
        │   ├── state_source.py    # The state interface and its data types
        │   ├── recording.py       # Loads and checks replay.json
        │   ├── recorded_source.py # State from a recording
        │   ├── motion.py          # Motion profile
        │   ├── layout.py          # Positions and sizes
        │   ├── playback.py        # Simulated clock
        │   ├── picking.py         # Crane or cell from a selection ray
        │   └── display_text.py    # Figures and details as text
        ├── appearance.py    # New: the only module that decides how objects look
        ├── scene.py         # New: builds and updates the USD scene
        ├── viewport_click.py # New: a click in the viewport as a selection ray
        ├── window.py        # New: controls, figures, details, and errors
        └── extension.py     # New: connects the parts

tests/
├── kit_runner.py            # New: finds and starts Kit for tests
├── omniverse/               # New: core logic, without Kit
├── viewer/                  # New: core logic compared with the browser viewer
├── omniverse_kit/           # New: scene and display in Kit, skipped without Kit
└── performance/             # New: SC-003, SC-004, and SC-005, in Kit

pyproject.toml               # Changed: test path, mypy files, marker, and version 0.4.0
README.md                    # Changed: setup and use of the Omniverse replay
```

**Structure Decision**: The extension lives in its own top-level folder, because it runs in Kit's Python and is not part of the installed `highbay_sim` package. Only `core/` is imported by the project's tests. The extension does not import `highbay_sim`, whose dependencies are not in Kit, and `highbay_sim` does not import the extension.

## Complexity Tracking

| Addition | Why Needed | Simpler Alternative Rejected Because |
|----------|------------|--------------------------------------|
| A Python copy of the browser's state, motion, layout, playback, and picking logic | Kit runs Python, and FR-006 and SC-002 require the same behavior as the browser replay | Running JavaScript in Kit adds a runtime and a bridge. Precalculating state into the recording changes the file format, grows it greatly, and leaves nothing a live source could reuse. A test comparing both copies at sampled times stops them drifting apart. |
| A second Python target (3.12 and 3.14) for the core modules | Kit's Python is fixed, and the project's environment uses 3.14 | Moving the project to 3.12 would change the simulation's environment for a feature that does not touch it |
| An optional test marker that needs Kit | Scene and display code can only run in Kit, and SC-008 needs all other tests to run without it | Manual checks alone would leave the scene unprotected against later changes |
