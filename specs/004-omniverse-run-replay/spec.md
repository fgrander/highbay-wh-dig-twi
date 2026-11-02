# Feature Specification: Omniverse Run Replay

**Feature Branch**: `004-omniverse-run-replay`

**Created**: 2026-11-02

**Status**: Draft

**Input**: User description: "Visualize a warehouse run in NVIDIA Omniverse with RTX rendering on the local computer with an RTX graphics card. A recorded run (event-based or time-stepped) is replayed in a Kit application: the warehouse layout is generated as OpenUSD scenes from the existing warehouse YAML, using simple parametric geometry for racks, cranes, load units and transfer points, with appearance replaceable later by detailed models. The Omniverse side only reads recorded data and contains no simulation logic; the simulation keeps running without Omniverse, and results stay unchanged. The data interface is designed so that a later feature can add a live connection to the time-stepped plant model without rebuilding the visualization. Out of scope: live coupling to the running plant model, any PLC connection, detailed CAD models, Nucleus or multi-user collaboration. The existing browser replay stays in place."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Replay a Recorded Run in Omniverse (Priority: P1)

A planner has a recorded run, either event-based or time-stepped. They open it in the Omniverse application and see the warehouse with its racks, cranes, load units, and transfer points in RTX rendering. They play the run, pause it, change its speed, and move to any point in time, and the cranes and load units show what the simulation recorded at that moment.

**Why this priority**: This is the capability the feature exists for. It is useful on its own, because a run can be shown and judged in a realistic rendering without any further step.

**Independent Test**: Can be fully tested by opening a recording of a sample warehouse, playing it, moving to several points in time, and comparing crane positions and load units with the recording.

**Acceptance Scenarios**:

1. **Given** a recorded run from either simulation mode, **When** the planner opens it, **Then** the warehouse appears with the racks, bays, and levels of the warehouse definition, and with the stock from the start of the run.
2. **Given** an open run, **When** the planner plays it, **Then** simulated time advances at the selected speed, and cranes move and load units appear, travel, and disappear as recorded.
3. **Given** an open run, **When** the planner moves to any point in time, forwards or backwards, **Then** the scene shows the same state as if the run had been played up to that point.
4. **Given** an open run, **When** the rendering frame rate changes, **Then** the state shown for a given simulated time stays the same.
5. **Given** a run has been replayed, **When** the planner compares the recording and the result files with their earlier state, **Then** nothing has changed.

---

### User Story 2 - Understand What Is Happening (Priority: P2)

While a run plays, the planner sees the simulated time, the activity of each crane, and the backlog per aisle. They can select a crane or a load unit to see its details, and jump to the first moment of the highest reported backlog.

**Why this priority**: A planner needs these figures to connect what they see with the throughput results. The rendering alone does not explain why an aisle falls behind.

**Independent Test**: Can be fully tested by replaying the overloaded sample warehouse, jumping to the highest backlog, and comparing the figures shown with the run's reported values.

**Acceptance Scenarios**:

1. **Given** a playing run, **When** a crane changes its activity, **Then** its displayed activity and appearance change at the recorded time.
2. **Given** an open run, **When** the planner selects a crane or load unit, **Then** its identity and current state are shown, including the order it serves if there is one.
3. **Given** an open run, **When** the planner jumps to the highest backlog, **Then** time moves to the first moment of the reported maximum, and the backlog shown equals the reported value.

---

### User Story 3 - Prepare for Live Data and Detailed Models (Priority: P3)

A developer extending the twin connects a different state source to the visualization, or replaces the look of an object type, without changing anything else in the visualization.

**Why this priority**: Live coupling and detailed models are later features. Keeping both open now avoids rebuilding the visualization, but neither delivers value to a planner yet.

**Independent Test**: Can be fully tested by driving the visualization from a scripted test source instead of a recording, and by replacing the look of the crane through its single defined place, with no other visualization change in either case.

**Acceptance Scenarios**:

1. **Given** a scripted test source that follows the defined state interface, **When** it is connected instead of a recording, **Then** the scene shows the states it delivers, with no change to scene or display logic.
2. **Given** a replacement look for an object type, **When** it is put in the defined place, **Then** that object type uses it, while positions and behavior stay the same.

### Edge Cases

- The chosen folder has no recording, or the recording is damaged: the application names the file and the problem, and it opens no partial scene.
- The recording has a format version that the application does not support: it refuses the file with a message naming both versions.
- A run has no orders or no events: the warehouse and its initial stock are shown, and playback runs through the empty time span.
- The speed is at its maximum and many events fall in one frame: every event still takes effect, and the state at each time stays correct.
- A replacement look is missing or cannot be loaded: the simple look is used, and a warning names the object type.
- The computer has no suitable graphics card or driver: the setup documentation names the requirement, and the simulation and browser replay remain usable.
- The warehouse is too large for the target frame rate: the replay stays correct in simulated time, at a lower frame rate.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Users MUST be able to open a recorded run from either simulation mode in the Omniverse application.
- **FR-002**: System MUST generate the warehouse scene from the warehouse data of the recorded run, and MUST NOT hard-code any layout.
- **FR-003**: The scene MUST show racks, cranes, load units, and transfer points as simple shapes, sized from the warehouse's dimensions, with RTX rendering.
- **FR-004**: Users MUST be able to play, pause, and restart a run, move to any time in it, and change its speed from 1× to 3,600×.
- **FR-005**: The state shown MUST depend only on the simulated time and the recorded data, and MUST NOT depend on frame rate, wall-clock time, or the order in which times were visited. Wall-clock time may only decide how fast simulated time advances during playback.
- **FR-006**: Crane motion between recorded events MUST follow the same motion profile as the browser replay.
- **FR-007**: The display MUST show simulated time, the measurement window, crane activity, and backlog per aisle.
- **FR-008**: Users MUST be able to select a crane or load unit and see its identity and current state.
- **FR-009**: Users MUST be able to jump to the first moment of the reported highest backlog.
- **FR-010**: The visualization MUST only read recorded data, MUST contain no simulation logic, and MUST NOT change any input, recording, or result file.
- **FR-011**: The simulation, its tests, and the browser replay MUST work on a computer without Omniverse, and simulation results MUST stay byte-identical to those from before this feature, except for the recorded software version.
- **FR-012**: The visualization MUST receive all run state through one defined state interface, so that a later live source can replace the recording without a change to scene or display logic. This feature MUST NOT connect to a running simulation or an external system.
- **FR-013**: The look of each object type MUST be decided in one defined place, so that a detailed model can replace a simple shape without a change to positions or behavior.
- **FR-014**: The application MUST reject a missing, damaged, or unsupported recording with a message that names the file and the problem.
- **FR-015**: Users MUST be able to move the view freely and return to a default view that shows the whole warehouse.
- **FR-016**: Generating a scene from identical recorded data and software version MUST give an identical scene.
- **FR-017**: Documentation MUST describe the graphics requirements, the setup of the Omniverse application including its license terms and data collection setting, and the steps to open a run, along with manual verification steps for anything that cannot be tested automatically.

### Key Entities

- **Recorded Run**: The stored record of one simulation run: its warehouse data, initial stock, orders, events, and reported values. It is the only data source in this feature.
- **Warehouse Scene**: The 3D representation generated from a warehouse's data, made of racks, cells, cranes, load units, and transfer points.
- **Run State**: What is true at one simulated time: crane positions and activities, where each load unit is, the backlog per aisle, and the orders in progress.
- **State Source**: Anything that delivers run state through the defined interface. A recording is the source in this feature, and a scripted test source proves the interface. A live plant model is a later source.
- **Object Look**: The appearance of one object type, separate from its position and behavior.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A planner can open a recording of the small sample warehouse and start playing it in under 60 seconds, not counting the first start of the application after setup.
- **SC-002**: At 100 sampled times in recordings from both simulation modes, crane positions deviate by no more than 1 cm from the browser replay's positions at the same times, and the location of every load unit matches.
- **SC-003**: The small sample warehouse plays at 30 frames per second or more at a resolution of 1920×1080 on the project owner's computer, with a graphics card of the RTX 3080 class.
- **SC-004**: A warehouse with 20 aisles and 100,000 storage locations opens in under 5 minutes and plays at 10 frames per second or more on the same computer.
- **SC-005**: Moving to any point in time in a one-day run on the small sample warehouse shows the correct state in under 1 second.
- **SC-006**: Figures shown at the jump to the highest backlog equal the run's reported values in 100% of the sample runs.
- **SC-007**: A scripted test source, written only from the state interface's documentation, drives the scene with no change to scene or display logic.
- **SC-008**: Result files for all sample scenarios stay byte-identical to those from before this feature, except for the recorded software version, and all existing tests pass on a computer without Omniverse.
- **SC-009**: A developer following the documentation can go from a fresh checkout to a replay in Omniverse in under 60 minutes, including downloads on a typical connection.

## Assumptions

- The application runs on the project owner's Windows computer with an RTX 3080 graphics card with 10 GB of memory. Other computers are not a target for this feature.
- The application uses a current Omniverse Kit release, installed separately from the simulation's environment. Its license terms have been accepted by the project owner.
- The recording made by the existing `--replay` option carries enough data for this feature. If the plan finds a gap, an extended recording must leave results unchanged and keep the browser replay working.
- The application reads files from the local computer. A shared server and collaboration between several users are out of scope.
- Only simple shapes are in scope. Detailed models and imported CAD data are a later feature, and no such data is available yet.
- Live coupling to the running plant model and any PLC connection are later features.
- The browser replay stays in place and remains the way to view runs on computers without an RTX graphics card.
- First-time shader compilation can take several minutes, and it is excluded from the opening times in SC-001 and SC-004.
- Performance values in SC-003, SC-004, and SC-005 are initial planning targets, and they may be refined when the plan measures real scenes.
