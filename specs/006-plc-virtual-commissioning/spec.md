# Feature Specification: PLC Virtual Commissioning

**Feature Branch**: `006-plc-virtual-commissioning`

**Created**: 2026-11-05

**Status**: Draft

**Input**: User description: "Start the PLC integration and interface. The PLC runs in S7-PLCSIM Advanced. The PLC controls and the model is the plant. There is only an empty CPU so far. Connect by symbolic access."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Prepare an Empty Simulated PLC (Priority: P1)

A controls engineer has a simulated CPU with no program. From a warehouse definition, they generate source files for the signal interface and for a crane control program, import them into the engineering tool, compile them, and download them to the simulated CPU.

**Why this priority**: The PLC is empty, so nothing else can run until it holds a program and an interface. These files can also be reviewed and tested without any connection.

**Independent Test**: Can be tested by generating the files for a sample warehouse and checking that every signal of the signal list appears for every crane, with the right type and direction. Compiling them needs the engineering tool, and is a manual step.

**Acceptance Scenarios**:

1. **Given** a warehouse with any number of aisles, **When** the engineer generates the files, **Then** the interface holds one complete set of signals for each crane.
2. **Given** the same warehouse and the same software version, **When** the engineer generates the files twice, **Then** the files are identical.
3. **Given** generated files, **When** the engineer imports and compiles them in the engineering tool, **Then** they compile with no errors.

---

### User Story 2 - Run the Warehouse Under PLC Control (Priority: P2)

The engineer runs a warehouse and scenario in time-stepped mode with the simulated PLC as the controller. In each cycle, the model writes order and plant signals to the PLC, reads the PLC's commands, and moves the cranes. At the end, the same reports as in any time-stepped run are written, and they state that a PLC was the controller.

**Why this priority**: This is the purpose of the feature: testing a control program against the plant model, with no real warehouse.

**Independent Test**: Can be tested with an in-memory stand-in for the PLC that runs a test controller, so that a whole run passes through the exchange without any Siemens software. This does not exercise the real connection, so final acceptance is a manual run on a real simulated CPU.

**Acceptance Scenarios**:

1. **Given** a simulated CPU with the generated program, **When** the engineer runs a sample scenario with it as the controller, **Then** all orders that the built-in controller finishes are also finished, and a report is written.
2. **Given** a running connection, **When** the PLC commands a crane, **Then** the plant reacts by the rules of the signal list, including its fault codes.
3. **Given** the connection is lost during a run, **When** the loss is detected, **Then** the run stops with a clear message, says in which cycle it stopped, and keeps what was recorded so far.

---

### User Story 3 - Refuse Anything but a Simulated PLC (Priority: P3)

Before the first write, the connection identifies the device. If it is not a simulated PLC, the run is refused and nothing is written.

**Why this priority**: The model writes values into the PLC. Signals that are harmless in a simulation could move real equipment, so this must be impossible by accident.

**Independent Test**: Can be tested with an emulated PLC that reports itself as a real CPU, and by confirming that no write reaches it.

**Acceptance Scenarios**:

1. **Given** a device that reports itself as a real CPU, **When** a run starts, **Then** it is refused before any write, with a message that names the device.
2. **Given** a device whose identity cannot be determined, **When** a run starts, **Then** it is refused in the same way.

---

### User Story 4 - Know What Cycle Time Is Possible (Priority: P3)

The engineer measures how fast signals can be exchanged, and which cycle times hold for a given number of cranes, before relying on a run.

**Why this priority**: Whether the default cycle of 50 ms can be held is unproven. A run that silently falls behind would give wrong results.

**Independent Test**: Can be tested by running the measurement against an emulated PLC and checking that it reports duration and missed cycles. Those numbers say nothing about a real simulated CPU, so they are reported as such.

**Acceptance Scenarios**:

1. **Given** a connection, **When** the engineer runs the measurement, **Then** they see the typical and slowest exchange time for the number of cranes in the warehouse.
2. **Given** a run in which an exchange takes longer than a cycle, **When** the run ends, **Then** the report states how many cycles overran and by how much.

### Edge Cases

- The interface in the PLC differs from the generated one, for example because of an older download: the run stops before its first cycle and names the missing or different signals.
- The PLC is in STOP when the run starts, or goes to STOP during it: the run does not start, or stops, with a message that says so.
- The PLC holds values from an earlier run: the run starts only after the job and command signals have been set to their starting values, and the model has confirmed them.
- Access to the PLC needs a password or a certificate that was not given: the run stops with a message that says what is missing, and does not show any secret.
- A rising edge on a command signal shorter than one exchange cycle would not be seen: the signal list rule that a signal stays false for at least one cycle before the next edge applies, and the generated program holds to it.
- The cycle time of the PLC program and that of the model differ: the exchange reads the latest values, and overruns are reported.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST generate, from a warehouse definition, source files for an interface block and a crane control program that a user can import into the engineering tool.
- **FR-002**: The generated interface MUST hold every signal of the current signal list for each crane, with names that follow directly from the signal list. The signal list version MUST be readable from the PLC.
- **FR-003**: The generated control program MUST carry out transport jobs by the same sequence as the built-in controller: to the source, pick, to the destination, set.
- **FR-004**: Users MUST be able to run a time-stepped simulation with a PLC as the controller, without changing how order handling, the plant model, or the reports work.
- **FR-005**: The connection MUST address signals by symbolic name, and MUST NOT depend on fixed memory addresses.
- **FR-006**: The system MUST identify the device before its first write, and MUST refuse any device that it cannot confirm to be a simulated PLC. No option MAY turn this off.
- **FR-007**: The system MUST check that the interface in the PLC matches the signal list before the first cycle, and MUST name each difference if not.
- **FR-008**: The system MUST report for each PLC run: that the controller was a PLC, the device identity, the signal list version, the cycle time, the number of overrun cycles, and the slowest exchange.
- **FR-009**: The report of a PLC run MUST state that the run is not reproducible, since it depends on a live PLC and on elapsed real time.
- **FR-010**: The system MUST provide a measurement of exchange time and held cycle time for a given number of cranes.
- **FR-011**: The system MUST stop a run with a clear message when the connection is lost or the PLC leaves RUN, and MUST keep what was recorded so far.
- **FR-012**: Connection details and secrets MUST come from outside the repository, and MUST NOT appear in reports or logs.
- **FR-013**: All automated tests MUST run with no Siemens software and no PLC. Runs that do not use a PLC MUST NOT need the connection library, and their results MUST NOT change.
- **FR-014**: The project constitution MUST be amended before implementation so that writing is allowed to simulated PLCs only, since Principle IV now forbids any write path.

### Key Entities

- **Signal Interface**: One set of signals per crane in the PLC, derived from the signal list and the warehouse, with the signal list version.
- **PLC Program Source**: The generated files to import, tied to a warehouse definition and a software version.
- **PLC Connection**: Where the PLC is and how to log in, given from outside the repository, along with the confirmed device identity.
- **PLC Run Record**: What a time-stepped run records, plus device identity, overruns, and the slowest exchange.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From an empty simulated CPU, an engineer who knows the engineering tool can reach a first PLC-controlled run in under 30 minutes by following the written steps.
- **SC-002**: In a sample scenario, a run under the generated PLC program finishes the same orders as the built-in controller, in a total time within 5% of it.
- **SC-003**: In 100% of the tested cases, a device that is not confirmed to be simulated receives no write.
- **SC-004**: With one crane at a cycle of 50 ms, at most 1% of the cycles overrun in a run of 10 minutes on a real simulated CPU. If this cannot be met, the measured limit is documented in place of it.
- **SC-005**: Every automated test passes on a machine with no Siemens software.
- **SC-006**: All results of existing runs without a PLC stay identical.

## Assumptions

- The controller is a simulated S7-1500 CPU in S7-PLCSIM Advanced, reached over TCP/IP. Other CPU families are out of scope.
- S7-PLCSIM Advanced and TIA Portal are not installed yet. The user installs them, accepts their licenses, and does the import, the compile, and the download. Criteria SC-001, SC-002, and SC-004, and the compile in User Story 1, stay open until then.
- Order handling stays in the model, as in the signal list. The PLC does not choose orders.
- The plant model stays ideal: drives have no position error, and safety functions are not modeled. The generated program is a starting point for commissioning, and is not safety-rated.
- A PLC run follows real time. Virtual time synchronized with the simulated CPU is out of scope for now.
- The connection library's documentation says that S7-PLCSIM Advanced V8.0 identifies itself as simulated. This has not been seen here, and is confirmed on the first real run. If the identity proves unreliable, the run is refused, and FR-006 needs another way.
- The connection library is young and unofficial. It is kept behind the existing controller interface, so that it can be replaced.
