# Feature Specification: Time-Stepped Plant Model

**Feature Branch**: `003-time-stepped-plant-model`

**Created**: 2026-11-02

**Status**: Draft

**Input**: User description: "Time-stepped plant model of the high-bay warehouse with a controller behind a defined signal interface, running headless in Python. The plant model simulates cranes, sensors and load units in fixed time steps and reacts to control signals (for example travel commands, positions, sensor states) cycle by cycle, the way a real plant reacts to a PLC. A built-in Python controller takes the role of the PLC for now and talks to the plant only through the signal interface, so that a real or simulated PLC can replace it later without changing the plant model. Results are reproducible and comparable with the existing event-based throughput simulation on the same warehouse and scenario. Out of scope for this feature: NVIDIA Omniverse visualization (a later feature on another computer with an RTX graphics card) and any actual PLC connection (a feature after that; the PLC vendor is still open, TwinCAT and Siemens are both candidates). The existing event-based simulation and 3D replay remain in place."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run a Warehouse Cycle by Cycle (Priority: P1)

A planner runs an existing warehouse and scenario in time-stepped mode, with no graphical interface. In every cycle, the built-in controller reads the plant's signals and sets its commands, and the plant model advances its cranes, sensors, and load units by one fixed time step. At the end, the planner receives the same kinds of results as from an event-based run.

**Why this priority**: This is the foundation of the feature. Without a plant that reacts cycle by cycle, neither a later PLC nor a later visualization has anything to connect to.

**Independent Test**: Can be fully tested by running a sample warehouse and scenario in time-stepped mode and confirming that all orders are processed through the signal interface and that a report is written.

**Acceptance Scenarios**:

1. **Given** a valid warehouse and scenario, **When** the planner starts a time-stepped run, **Then** the run completes without any graphical interface and writes a report with the same metrics and definitions as an event-based run.
2. **Given** a running simulation, **When** a cycle is processed, **Then** the controller sees only the signals defined by the signal interface, and the plant changes only in response to commands in that interface and to the passing of time.
3. **Given** the same inputs, seed, cycle time, and software version, **When** the run is repeated, **Then** all results are identical.
4. **Given** a chosen cycle time, **When** a run completes, **Then** its outputs record the mode and the cycle time used.
5. **Given** a time-stepped run has been added to the software, **When** an event-based run is started with the same inputs, **Then** its results are unchanged.

---

### User Story 2 - Compare With the Event-Based Simulation (Priority: P2)

A planner runs the same warehouse and scenario in both modes and compares the results, to trust that the plant model and the controller behave like the already verified simulation, and to see how far any deviation goes.

**Why this priority**: The event-based simulation is verified against hand calculations. Agreement with it is what makes the new model credible, but the model must exist first.

**Independent Test**: Can be fully tested by running the verification scenarios and a sample scenario in both modes, then comparing completion times and throughput with the stated tolerances.

**Acceptance Scenarios**:

1. **Given** a verification scenario with hand-calculated results, **When** it runs in time-stepped mode, **Then** order completion times match the calculated values within the tolerance in SC-003.
2. **Given** a warehouse and scenario, **When** the planner compares a time-stepped run with an event-based run, **Then** the comparison shows the deviation of each throughput metric from the event-based result.
3. **Given** a warehouse and scenario, **When** the planner shortens the cycle time, **Then** the deviation from the event-based result does not grow beyond the tolerance in SC-004.

---

### User Story 3 - Replace the Controller Through the Signal Interface (Priority: P3)

An automation engineer reads the written signal list and connects a different controller to the plant model, without changing the plant model. The engineer can then read a record of the signals, cycle by cycle, to see what the controller commanded and how the plant reacted. This prepares the later connection of a PLC.

**Why this priority**: Being replaceable is the main reason for building the model this way. It is proved here with a second controller, while an actual PLC connection remains a later feature.

**Independent Test**: Can be fully tested by driving the plant with a separate, scripted test controller that uses only the written signal list, and confirming that a load unit is stored and retrieved as expected.

**Acceptance Scenarios**:

1. **Given** the written signal list, **When** a scripted test controller drives the plant through a storage and a retrieval, **Then** the load unit ends up where expected, with no change to the plant model.
2. **Given** a controller sends a command that the plant cannot carry out, **When** the cycle is processed, **Then** the plant stays physically consistent, reports a fault signal, and records the cause.
3. **Given** a run with signal recording switched on, **When** it completes, **Then** the planner can read every change of every signal with its cycle and simulated time.
4. **Given** a run with signal recording switched off, **When** its results are compared with those of a run with recording on, **Then** they are identical.

---

### User Story 4 - Replay a Time-Stepped Run in 3D (Priority: P4)

A planner opens a time-stepped run in the existing 3D replay, and sees cranes and load units move as they did in that run.

**Why this priority**: It reuses the existing viewer to check the model by eye, and it is useful preparation for a later visualization, but the model is complete without it.

**Independent Test**: Can be fully tested by writing a replay from a time-stepped run, opening it in the existing viewer, and comparing crane positions at chosen times with the plant's recorded positions.

**Acceptance Scenarios**:

1. **Given** a completed time-stepped run, **When** the planner opens it in the 3D replay, **Then** the viewer shows the run without any change in how the planner uses it.
2. **Given** a time at a cycle boundary, **When** the planner compares the viewer's crane position with the plant's recorded position, **Then** they agree within the tolerance in SC-006.

---

### Edge Cases

- The cycle time is zero, negative, or too long for the warehouse's motion to be represented: the run is rejected before it starts, with a message that names the value and the allowed range.
- A command arrives while a crane is already moving, or targets a location outside the warehouse: the plant does not carry it out, and it reports a fault signal.
- A controller commands a pick from an empty location, or a set into an occupied location: the plant reports a fault signal, and no load unit is created, lost, or duplicated.
- A controller stops issuing commands while orders remain: the run ends at the scenario's end with the open orders reported as backlog, and with no failure.
- A fault stays active: the affected crane remains stopped until the controller acknowledges the fault, and the other cranes continue.
- Two events fall between the same two cycle boundaries: they take effect at the next boundary, in a fixed and documented order, so that results stay reproducible.
- A movement ends between two cycle boundaries: the crane stops exactly at its target and never overshoots it.
- The scenario ends during a movement: the end state and open orders are reported in the same way as in an event-based run.
- A warehouse with no stock, or with no possible storage location: this behaves as in an event-based run, including orders that wait or are unfulfillable.

## Requirements *(mandatory)*

### Functional Requirements

**Plant model**

- **FR-001**: The system MUST simulate the warehouse in fixed time steps, with the plant model advancing cranes, sensors, and load units once per cycle.
- **FR-002**: The plant model MUST use the same warehouse definition, crane parameters, and input validation as the event-based simulation, so that no input file needs to change.
- **FR-003**: The cycle time MUST be selectable per run within a documented range, and MUST be recorded in the run's outputs.
- **FR-004**: Crane motion in the plant model MUST use the same speed and acceleration limits as the event-based simulation, and MUST stop exactly at its target.
- **FR-005**: The plant model MUST keep load units physically consistent: each load unit is in exactly one place at any time, and is never created, lost, or duplicated by a command.
- **FR-006**: The plant model MUST reject a command that it cannot carry out, keep its state consistent, set a fault signal, and record the cause. A fault MUST hold only the affected crane until acknowledged.

**Signal interface**

- **FR-007**: All exchange between controller and plant MUST pass through a single signal interface. A controller MUST NOT read or change any other plant state.
- **FR-008**: Each signal MUST have a written definition with its name, direction, data type, unit, and meaning. The signal list MUST carry a version, which MUST be recorded in the run's outputs.
- **FR-009**: The signals MUST be per-axis positioning signals: a controller sets a target position and a start for each axis and commands load handling, and the plant's simulated drives carry out the motion and report the actual position, whether the target is reached, the load sensor state, and faults.
- **FR-010**: The signal interface MUST be organized per crane and MUST work for any number of aisles, with no change to its definition.
- **FR-011**: A controller MUST take over crane control only. Order sequence and storage location choice MUST stay in the simulation's order handling, which gives the controller transport orders (source, destination) and receives their completion through the signal interface.
- **FR-012**: The plant model MUST NOT depend on which controller is connected, nor on how the controller is built.

**Controller and execution**

- **FR-013**: The system MUST include a built-in controller that carries out all transport orders using only the signal interface. The order handling MUST apply the warehouse's storage location rule and the same order rules as the event-based simulation.
- **FR-014**: Each cycle MUST run in a fixed sequence: the controller reads signals, the controller sets commands, the plant advances by one time step.
- **FR-015**: Simulated time MUST be independent of wall-clock time and of the speed of the computer. A run MUST wait for its controller in each cycle, rather than proceed without it.
- **FR-016**: Users MUST be able to choose a different controller for a run, without any change to the plant model.

**Results and records**

- **FR-017**: A time-stepped run MUST report the same throughput metrics, with the same definitions, units, and measurement window, as an event-based run.
- **FR-018**: Users MUST be able to compare a time-stepped run with an event-based run of the same inputs, and see the deviation of each metric.
- **FR-019**: Users MUST be able to switch on a record of signal changes, with the cycle and simulated time of each change. Recording MUST NOT change the results.
- **FR-020**: A time-stepped run MUST be able to write a replay file that the existing 3D replay can open.
- **FR-021**: The event-based simulation and the 3D replay MUST remain available, and event-based results MUST NOT change, except for the recorded software version.
- **FR-022**: Invalid run settings MUST be rejected before the run starts, with a message identifying the setting and the allowed values.
- **FR-023**: Modeling assumptions and simplifications of the plant model and the signal interface MUST be documented, including every known source of deviation from the event-based simulation.

### Key Entities

- **Plant Model**: The simulated warehouse equipment and its state: cranes, sensors, load units, and cells. It changes only through the passing of cycles and through commands.
- **Cycle**: One fixed time step, in which the controller reads signals and sets commands, and the plant advances.
- **Signal**: A named value exchanged between controller and plant, with a direction, data type, unit, and meaning.
- **Signal List**: The versioned written definition of all signals. It is the contract that a later PLC connection builds on.
- **Controller**: Anything that reads and sets signals in each cycle to control the cranes. The built-in controller is the first one, and a scripted test controller is the second.
- **Order Handling**: The part of the simulation that keeps the order sequence, chooses storage locations, and issues transport orders. It stays in the simulation when the controller is replaced.
- **Transport Order**: One crane job with a source and a destination, passed to the controller through the signal interface, and reported back when complete.
- **Fault**: A plant signal that a command could not be carried out, with its cause. It holds the affected crane until acknowledged.
- **Signal Record**: The optional list of signal changes in a run, with cycle and simulated time.
- **Run**: As in the event-based simulation, extended by its mode, cycle time, controller, and signal list version.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A planner can go from an existing warehouse and scenario to a complete time-stepped report with a single start action, with no graphical interface and no changes to the input files.
- **SC-002**: In 10 repeated runs of the same inputs, seed, and cycle time, including on differently loaded machines, 100% of reported metrics are identical.
- **SC-003**: In verification scenarios with hand-calculated results, each order's completion time deviates from the calculated value by no more than 2 cycles for each movement or handling step of that order.
- **SC-004**: On the sample warehouses and scenarios, total, storage, and retrieval throughput each deviate from the event-based result by no more than 1% or one completed order, whichever is larger, both at the default cycle time and at one tenth of it.
- **SC-005**: A warehouse with 20 aisles and 100,000 storage locations can simulate one hour of operation at 1,000 orders per hour and the default cycle time in under 60 seconds on a typical desktop computer.
- **SC-006**: In a replayed time-stepped run, crane positions at cycle boundaries deviate from the plant's recorded positions by no more than 1 cm.
- **SC-007**: A scripted test controller, written only from the signal list, completes a storage and a retrieval with no change to the plant model.
- **SC-008**: In a test set of invalid commands, 100% produce a fault signal with a recorded cause, and the count and locations of load units remain consistent in every case.
- **SC-009**: Event-based results for all sample scenarios stay byte-identical to those from before this feature, except for the recorded software version.

## Assumptions

- The scope is headless simulation. NVIDIA Omniverse visualization is a later feature on another computer with an RTX graphics card, and it will read the plant model's state.
- Any actual PLC connection, including its protocol, real-time operation, and vendor, is a later feature. TwinCAT and Siemens are both candidates, so the signal list stays vendor-neutral.
- A later PLC program is expected to control its drives in positioning mode. A PLC with its own position control would need a further, lower-level signal set.
- Later PLC connections will need a change to the constitution, because signals are written towards a controller. This feature connects to no external system and needs no such change.
- The default cycle time is 50 ms, as an initial value in the range of typical PLC task times, and short enough to keep its effect on throughput clearly below the limit in SC-004. It can be changed per run.
- Handling a load takes the existing pick and set times from the crane parameters. Detailed fork motion is not modeled.
- Cranes do not break down on their own. Faults arise only from commands that the plant cannot carry out; fault injection for testing PLC programs is a later extension.
- Drive dynamics, position control errors, and sensor noise are not modeled, so an ideal drive follows the speed and acceleration limits exactly.
- Safety functions such as emergency stops and light curtains are not modeled.
- Warehouses contain one crane per aisle, as in the event-based simulation.
- Scale and performance values in SC-005 are initial planning targets, because no specific warehouse has been named yet.
- The tolerances in SC-003, SC-004, and SC-006 are initial values. They may be refined when the plan identifies the sources of deviation.
