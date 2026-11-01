# Feature Specification: 3D Run Replay

**Feature Branch**: `002-3d-run-replay`

**Created**: 2026-11-01

**Status**: Draft

**Input**: User description: "3D visualization of the warehouse and its cranes that replays a simulation run."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Watch a Run Replay in 3D (Priority: P1)

A warehouse planner opens a completed simulation run and sees the warehouse in 3D: its racks, cells, aisles, transfer points, and cranes. The planner plays the run, and cranes move through their aisles and carry load units between transfer points and cells, exactly as they did in the simulation. The planner can pause, change the speed, and jump to any moment.

**Why this priority**: This is the core value of the feature. Seeing the run makes crane movements and bottlenecks understandable without reading tables, and it builds on the existing simulation without changing it.

**Independent Test**: Can be fully tested by running the sample warehouse and scenario, opening the run in the viewer, playing it, and confirming that crane positions and stored load units match the run's per-order results at chosen times.

**Acceptance Scenarios**:

1. **Given** a completed run, **When** the planner opens it, **Then** the viewer shows the warehouse with the defined number of aisles, racks, bays, and levels, the defined cell dimensions, all transfer points, and one crane per aisle.
2. **Given** an opened run, **When** the planner starts playback, **Then** simulated time advances, cranes move as recorded, and load units appear on cranes and in cells at their recorded times.
3. **Given** a playing run, **When** the planner pauses, changes the speed, or moves to another time, **Then** the view immediately shows the exact state at the resulting simulated time.
4. **Given** the same run, **When** the planner jumps to one moment directly or reaches it through playback, **Then** both show the same crane positions and the same stored load units.
5. **Given** a run has been viewed, **When** the planner compares its result files with those from before viewing, **Then** the files are unchanged.

---

### User Story 2 - Navigate and Inspect (Priority: P2)

A planner looks around the warehouse from any angle, and selects a crane, cell, or load unit to see what it is doing, what it holds, and which order it belongs to.

**Why this priority**: Inspection explains what the planner sees and connects the 3D view to the per-order results, but the replay is already useful without it.

**Independent Test**: Can be fully tested by opening a run, moving the camera, selecting objects at chosen times, and comparing the details shown with the run's per-order results.

**Acceptance Scenarios**:

1. **Given** an opened run, **When** the planner rotates, moves, or zooms the view, **Then** the camera changes without affecting simulated time or playback, and the planner can return to a default view that shows the whole warehouse.
2. **Given** a crane at a chosen time, **When** the planner selects it, **Then** the viewer shows its number, current activity, current order, and the destination of its current movement.
3. **Given** a cell at a chosen time, **When** the planner selects it, **Then** the viewer shows its location and state, and the article of any load unit it holds.
4. **Given** a load unit at a chosen time, **When** the planner selects it, **Then** the viewer shows its article and the related order, with that order's arrival, start, and completion times where available.

---

### User Story 3 - Spot Bottlenecks During Replay (Priority: P3)

A planner watches for problems: which cranes are busy or idle, where orders are waiting, and how results develop over simulated time. The planner can jump directly to the moment of the highest backlog.

**Why this priority**: This turns the replay into an analysis tool, for example to see one aisle overloaded while others are free. It depends on the replay in User Story 1.

**Independent Test**: Can be fully tested by replaying a run in which one aisle is overloaded, then confirming that the crane states, backlog per aisle, and live figures show the imbalance and agree with the run's reported metrics.

**Acceptance Scenarios**:

1. **Given** a playing run, **When** a crane changes activity, **Then** its appearance shows whether it is moving empty, moving loaded, handling a load, or idle.
2. **Given** a chosen time, **When** the planner reads the on-screen figures, **Then** they show the simulated time, the backlog in total and per aisle, the occupancy, and the orders completed so far, and whether the time is in the warm-up or the measurement window.
3. **Given** the end of a run, **When** the planner compares the on-screen figures with the run's report, **Then** the orders completed, backlog, and occupancy match.
4. **Given** an opened run, **When** the planner chooses to go to the highest backlog, **Then** the view jumps to the first moment in the measurement window at which the backlog reaches its reported maximum.

---

### Edge Cases

- A run has no orders: the warehouse and its initial stock are shown, playback works, and all counts stay at zero.
- An order is unfinished at the end of the run: its movement stops at the end of the run, and any load unit stays where it was at that moment.
- An unfulfillable order causes no crane movement or load unit, and is still counted in the on-screen figures.
- A storage order is waiting for a free cell: it counts as backlog, but no load unit appears until a crane picks it up.
- An activity has zero duration, for example when a crane is already at its destination or handling time is zero: playback continues without a visible gap or error.
- Playback reaches the end of the run: it stops at the final state, and can be restarted or moved back.
- The planner moves the time beyond the start or end of the run: the time stays within the run.
- A replay file is missing, damaged, or was written by an incompatible version: the viewer shows a clear message explaining the problem and displays no partial state.
- A warehouse has few cells or many: the default view always shows the whole warehouse, whatever its size.

## Requirements *(mandatory)*

### Functional Requirements

**Replay data**

- **FR-001**: System MUST be able to write replay data for a simulation run, containing the warehouse geometry, initial stock, every crane activity, every load unit movement, and every order state change, so that a run can be viewed without simulating it again.
- **FR-002**: Replay data MUST be produced only by observing a run. Writing it MUST NOT change any result, and the existing result files MUST remain byte-identical with or without it.
- **FR-003**: Replay data MUST be byte-identical for identical inputs, seed, and software version.
- **FR-004**: Replay data MUST identify its run with the same warehouse and scenario hashes, seed, software version, and measurement window as the run's results, and MUST state its own format version.
- **FR-005**: Simulation runs MUST continue to work with no display. Producing replay data MUST NOT require a display.

**Viewer**

- **FR-006**: Users MUST be able to open a run's replay data in the viewer, which runs in a web browser on the planner's own computer, with no separate installation for the viewer and no internet connection.
- **FR-007**: The viewer MUST show racks, cells, aisles, transfer points, cranes, and load units, with positions and sizes taken from the warehouse definition, drawn as simple geometric shapes. The appearance of each object type MUST be defined separately from replay and playback behavior, so that detailed models can replace the shapes later without changing replay data or playback behavior.
- **FR-008**: The viewer MUST NOT calculate simulation results or change a run's inputs, results, or replay data. It only reads replay data.
- **FR-009**: The viewer MUST show a clear message when replay data is missing, damaged, or of an incompatible format version, and MUST NOT show partial state in that case.

**Playback**

- **FR-010**: Users MUST be able to play and pause, restart, move to any simulated time, and choose a playback speed from at least 1, 10, 60, 600, and 3,600 times real time.
- **FR-011**: Crane positions at any simulated time MUST follow the same motion calculation as the simulation, with horizontal and vertical travel at the same time, so the replay shows acceleration and braking.
- **FR-012**: The state shown at a simulated time MUST depend only on that time and the replay data, not on how the planner reached it.
- **FR-013**: Load units MUST appear at their inbound transfer point when picked, on the crane while carried, in their cell while stored, and leave at the outbound transfer point when set down. Initial stock MUST be visible from the start.

**Navigation and inspection**

- **FR-014**: Users MUST be able to rotate, move, and zoom the view, and return to a default view showing the whole warehouse.
- **FR-015**: Users MUST be able to select a crane, cell, or load unit, and see the details in User Story 2 for the current simulated time.
- **FR-016**: Load units of different articles MUST be visually distinguishable, and the viewer MUST show which appearance belongs to which article.

**Analysis**

- **FR-017**: Each crane's appearance MUST show its current activity: moving empty, moving loaded, handling, or idle.
- **FR-018**: The viewer MUST show at all times the simulated time, whether it is in the warm-up or the measurement window, total backlog, backlog per aisle, occupancy, and orders completed so far.
- **FR-019**: At the end of a run, the viewer's order counts, backlog, and occupancy MUST match the run's reported values for the same scope.
- **FR-020**: Users MUST be able to jump to the first moment in the measurement window at which the backlog reaches its reported maximum.

### Key Entities

- **Replay Data**: The saved record of one run for viewing: run identification, format version, warehouse geometry, initial stock, and time-ordered changes.
- **Replay State**: What exists at one simulated time: crane positions and activities, stored and carried load units, cell states, and order counts. It is derived entirely from replay data and a time.
- **Playback Session**: The planner's current simulated time, playing or paused state, speed, camera, and selection. It belongs to the viewer and changes no run data.
- **Crane, Storage Location, Transfer Point, Load Unit, Article, Order**: As in the headless throughput simulation (`specs/001-headless-throughput-sim/spec.md`).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A planner can go from a completed sample run to a playing 3D replay in under 1 minute, using only the project's documentation.
- **SC-002**: At the warehouse size in the simulation's planning target (20 aisles, 100,000 cells, 24 simulated hours at 1,000 orders per hour), playback and camera movement stay smooth, at 30 frames per second or more, on a typical desktop computer with 3D-capable graphics.
- **SC-003**: At the same size, moving to any simulated time shows the correct state in under 1 second.
- **SC-004**: In verification scenarios with hand-calculated results, crane positions at chosen times deviate by no more than 1 cm from the calculated values.
- **SC-005**: In 100% of tested times, moving directly to a time and reaching it through playback give the same crane positions, stored load units, and on-screen counts.
- **SC-006**: At the end of a replay, the orders completed, backlog, and occupancy shown are identical to the run's report in 100% of tested runs.
- **SC-007**: Result files are byte-identical with and without replay data being written, in 100% of tested runs, and identical inputs give byte-identical replay data.
- **SC-008**: Replay data for the planning-target run takes no more than 100 MB of disk space, and writing it adds no more than 30 seconds to that run.

## Assumptions

- Users are the same planners as for the simulation, working on their own computer. Accounts, sharing, and network access are not needed.
- Replay happens after a run has finished. Watching a run while it simulates, and live data from real warehouse systems, are out of scope and remain possible later through the simulation's event stream and data source interfaces.
- The viewer shows one run at a time. Comparing two runs side by side is out of scope.
- The viewer is read-only: editing warehouse designs or scenarios in 3D, exporting videos or images, and virtual reality are out of scope.
- Detailed 3D models of cranes, racks, wood panel packages, and paper stacks are out of scope for this feature and may be added later.
- The requirement that the simulation runs entirely in Python applies to the simulation, not to the viewer.
- The simulation does not define the distance between aisles, so the viewer uses a fixed spacing based on the cell width for display only. It has no effect on results.
- Fork movements are not simulated, so handling is shown as a crane state without an animated fork. Load units change position at the end of the pick and set steps.
- Cell width, which does not affect simulation travel, is used for the display of cells.
- Transfer points are shown as marked positions at the aisle ends. Conveyors and the arrival or departure of load units beyond them are not modeled.
- Replay data is written only when the planner asks for it, so existing commands and result files keep working unchanged.
- Performance values in SC-002, SC-003, and SC-008 are initial planning targets, because no specific warehouse has been named yet.
