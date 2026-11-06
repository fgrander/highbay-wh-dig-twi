# Highbay Warehouse Digital Twin Constitution

## Core Principles

### I. Simulation Core Independent of Visualization

The simulation MUST run without the 3D visualization, including headless and in automated tests.
The visualization MUST only read simulation state and send commands through a defined interface;
it MUST NOT contain simulation logic or determine simulation results.

Rationale: throughput results must not depend on rendering, and each part must be testable alone.

### II. Reproducible Simulation

Identical warehouse layout, parameters, input data, random seed, and software version MUST produce
identical results. Simulation time MUST be independent of rendering frame rate and wall-clock time.
All sources of randomness MUST be seeded and the seed MUST be recorded with each run.
A run coupled to a live simulated PLC is exempt from this principle, because it follows real time.
Its report MUST state that it is not reproducible.

Rationale: scenarios can only be compared, and defects only reproduced, if runs are repeatable.

### III. Credible Throughput Results

Every throughput metric MUST have a written definition stating what is counted, its unit, and its
measurement window. Each result MUST be traceable to the layout, parameters, and assumptions that
produced it. Modeling assumptions and simplifications MUST be documented, and metric calculations
MUST be verified against scenarios with independently known results.

Rationale: a simulation only supports decisions when its numbers can be explained and checked.

### IV. Live Data as a Later, Pluggable Option

The system MUST be fully usable without any connection to a real warehouse system. All data MUST
enter through a defined data source interface so that a live source can be added later without
changing simulation or visualization logic. Live integration MUST NOT be built until a feature spec
calls for it. Live connections MUST be read-only towards real warehouse systems and real PLCs.
Writing is allowed only to a simulated PLC, whose identity MUST be confirmed before the first write.
Any device that cannot be confirmed as simulated MUST be refused. Any other write path requires a
constitution amendment.

Rationale: this keeps the live option open at low cost, and the twin must never be able to affect
real warehouse equipment by accident. Virtual commissioning needs a PLC that reads the plant's status
from the model, so writing to a simulated PLC is allowed, while a real PLC stays out of reach.

### V. Test-First Simulation Logic

Simulation logic and metric calculations MUST be developed test-first: tests are written, confirmed
to fail, and then made to pass. Visualization code MUST have automated tests where practical and
MUST otherwise have documented manual verification steps.

Rationale: errors in simulation logic produce plausible but wrong numbers that are hard to notice.

### VI. Incremental Delivery and Simplicity

Each feature MUST deliver an independently demonstrable capability. Added complexity, including new
abstractions and dependencies, MUST solve a current requirement and MUST be justified in the
implementation plan. Interfaces required by Principles I and IV are exempt from this justification.

Rationale: the scope is broad, and small working increments expose modeling problems early.

## Technical Constraints

- Warehouse layouts and simulation scenarios MUST be defined as versionable data, not hard-coded.
- Each feature spec that affects performance MUST state measurable targets, such as frame rate,
  simulation speed, and supported warehouse size, until project-wide targets are set here.
- Target platforms and the technology stack are chosen in the implementation plan of the first
  feature, and MUST satisfy the principles above.
- Credentials and connection details for external systems MUST NOT be committed to the repository.

## Development Workflow

- Work MUST follow the Spec Kit sequence: specification, plan, tasks, then implementation.
- Each feature MUST be developed on its own feature branch.
- Each implementation plan MUST include a constitution check and MUST record any justified deviation.
- All automated tests MUST pass before a feature branch is merged.
- Changes that alter simulation results MUST be identified as such in the commit or pull request.

## Governance

This constitution takes precedence over other project practices. Amendments MUST be documented in
this file with their rationale and MUST be approved by the project owner.

Versioning follows semantic versioning: MAJOR for removing or redefining a principle or governance
rule incompatibly, MINOR for adding a principle or section or materially expanding guidance, and
PATCH for clarifications and wording fixes.

Compliance is verified in each implementation plan's constitution check and before merging a feature.

**Version**: 1.1.0 | **Ratified**: 2026-11-01 | **Last Amended**: 2026-11-05
