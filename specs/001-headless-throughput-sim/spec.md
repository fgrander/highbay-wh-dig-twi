# Feature Specification: Headless Throughput Simulation

**Feature Branch**: `001-headless-throughput-sim`

**Created**: 2026-11-01

**Status**: Draft

**Input**: User description: "Headless throughput simulation of one configurable high-bay warehouse: define the layout and storage/retrieval equipment as data, run a seeded order scenario, and report defined throughput metrics."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run a Throughput Simulation (Priority: P1)

A warehouse planner describes one high-bay warehouse (layout and storage/retrieval equipment) and an order scenario in data files, starts a simulation run without any graphical interface, and receives a report of throughput metrics for the simulated period.

**Why this priority**: This is the core value of the feature. Without it, there are no throughput numbers to act on, and later features such as the 3D view have nothing to build on.

**Independent Test**: Can be fully tested by running a sample warehouse and a seeded scenario with no display available, then confirming that a complete metrics report is produced.

**Acceptance Scenarios**:

1. **Given** a valid warehouse definition and a seeded order scenario, **When** the planner starts a run, **Then** the run finishes without a graphical interface and produces a report containing every metric defined in FR-012.
2. **Given** a completed run, **When** the planner starts another run with the same inputs, seed, and software version, **Then** every reported metric is identical.
3. **Given** the same inputs with a different seed, **When** the planner starts a run, **Then** a different order sequence is generated and the report records the seed that was used.
4. **Given** a warehouse definition containing an error, **When** the planner starts a run, **Then** no simulation starts and the planner sees every validation problem found, with its location in the input.

---

### User Story 2 - Verify and Trace Results (Priority: P2)

A planner who must defend a result to colleagues checks what each number means, which inputs produced it, and whether the simulation matches results that can be worked out by hand.

**Why this priority**: Throughput numbers only support decisions if they can be explained and checked. This builds on the run in User Story 1.

**Independent Test**: Can be fully tested by running a small scenario with an explicit order list whose timing is calculated by hand, then comparing the report to the calculated values and checking the recorded inputs.

**Acceptance Scenarios**:

1. **Given** an explicit order list and a warehouse with a single crane, **When** the run completes, **Then** order completion times match the independently calculated values within the tolerance in SC-003.
2. **Given** any completed run, **When** the planner reads the report, **Then** it identifies the warehouse definition, scenario, seed, software version, and measurement window used, and defines each metric's meaning and unit.
3. **Given** any completed run, **When** the planner reviews the per-order results, **Then** each order's arrival, start, and completion times, or its reason for not completing, can be found.

---

### User Story 3 - Compare Warehouse Variants (Priority: P3)

A planner changes the warehouse design, such as the number of aisles, crane speed, or the storage location rule, by editing data only, runs the same scenario again, and compares the throughput results of the variants.

**Why this priority**: Comparing alternatives is the main use of the results, but it requires reliable single runs first.

**Independent Test**: Can be fully tested by running two warehouse definitions that differ only in crane speed against the same scenario, then confirming that the results are directly comparable and that, in a scenario with the same cell assignments, the faster variant has shorter order execution times (completion minus start).

**Acceptance Scenarios**:

1. **Given** a warehouse definition, **When** the planner changes its dimensions or equipment parameters in the data, **Then** the next run uses the new values without any software change.
2. **Given** two variants and one scenario definition with the same seed, **When** both are run, **Then** both runs process the same order sequence wherever both warehouses can hold the same articles.
3. **Given** two completed runs, **When** the planner compares their machine-readable results, **Then** the same metrics appear under the same names and units.
4. **Given** a warehouse definition, **When** the planner changes the number of aisles in the data, **Then** the next run has one crane and the defined transfer points per aisle, and the report shows utilization for each crane.
5. **Given** a warehouse definition, **When** the planner moves or adds inbound or outbound transfer points at either aisle end in the data, **Then** the next run uses them without any software change.

---

### Edge Cases

- A retrieval order names an article that has no stock: the order is marked as unfulfillable with that reason, counted separately, and the run continues.
- A storage order arrives while no location is free: the order waits until a location becomes free, or is reported as unfinished if the run ends first.
- The scenario contains no orders: the run completes and reports zero throughput rather than failing.
- No order completes within the measurement window: throughput is reported as zero, and metrics that have no data are shown as not available rather than zero.
- Orders remain open when the simulated period ends: they are excluded from completed counts and reported as unfinished.
- The warm-up period is equal to or longer than the simulated period: the input is rejected at validation because the measurement window would be empty.
- Input refers to a location, aisle, or crane that does not exist, or the aisle count, a cell dimension, a cell count, or an equipment parameter is zero or negative: the input is rejected at validation.
- An aisle has no inbound transfer point or no outbound transfer point: the input is rejected at validation.
- Initial stock exceeds the warehouse's capacity or occupies the same location twice: the input is rejected at validation.

## Requirements *(mandatory)*

### Functional Requirements

**Warehouse definition**

- **FR-001**: Users MUST be able to define one warehouse in a versionable data file, including a freely chosen number of aisles, racks per aisle, and freely chosen values for the height, length, and width of its storage cells and the number of cells (through bays and levels). Cell length, cell height, and cell positions MUST determine crane travel distances. Cell width MUST be validated and recorded, but does not affect travel, because cranes do not change aisles and fork movement is part of the handling time.
- **FR-001a**: Users MUST be able to define for each aisle, at each of its two ends, whether it has an inbound transfer point, where the crane picks up load units for storage, an outbound transfer point, where the crane sets down retrieved load units, or both. Each aisle MUST have at least one inbound and one outbound transfer point. Crane travel to and from these transfer points MUST be part of each order's movement.
- **FR-001b**: When an aisle has more than one transfer point of the required type, System MUST use the one that gives the order the shortest total crane travel time.
- **FR-002**: Users MUST be able to define storage/retrieval equipment in data, including travel speed, acceleration, and load-handling time. Supported equipment is aisle-bound stacker cranes, one per aisle. Conveyors and shuttle systems are out of scope for this feature.
- **FR-003**: Users MUST be able to define initial stock by article and storage location in data, and to choose the storage location rule from at least random free location and nearest free location, where nearest means the shortest crane travel time from an inbound transfer point of the location's aisle. Both rules and retrievals MUST consider all aisles.
- **FR-004**: System MUST validate all inputs before starting a run, and MUST report every problem found together with its location in the input.

**Order scenario**

- **FR-005**: Users MUST be able to define a scenario from generation parameters and a seed, including order rate, storage/retrieval mix, article distribution, and simulated duration.
- **FR-006**: Users MUST be able to supply an explicit list of timed orders as an alternative to generated orders.
- **FR-007**: An order MUST represent storing or retrieving exactly one load unit. A load unit is a package of wood panels or a stack of paper on a pallet. Customer orders with several lines are out of scope for this feature.

**Simulation**

- **FR-008**: System MUST run with no graphical interface and no display available.
- **FR-009**: System MUST produce identical results for identical inputs, seed, and software version, regardless of the machine's speed or load.
- **FR-010**: System MUST calculate each crane movement from the defined distance, speed, acceleration, and handling time, with horizontal and vertical travel occurring at the same time.
- **FR-011**: System MUST let users set a warm-up period, and MUST calculate metrics only from the measurement window that follows it.

**Reporting**

- **FR-012**: System MUST report the following metrics, each with its written definition and unit in the report:
  - **Throughput**: orders completed per hour in the measurement window, in total and separately for storage and retrieval. An order is completed when its load has been set down at its destination location or transfer point.
  - **Order cycle time**: time from an order's arrival to its completion, for orders completed in the window, as mean, median, 95th percentile, and maximum.
  - **Order waiting time**: time from an order's arrival until a crane starts working on it, with the same statistics.
  - **Crane utilization**: for each crane, the share of the window spent moving loaded, moving empty, handling a load, and idle.
  - **Backlog**: number of orders waiting at the end of the window, and the highest number during the window.
  - **Storage occupancy**: share of locations occupied at the start and end of the window.
  - **Order outcomes**: number of orders that were generated, completed, unfinished, and unfulfillable.
- **FR-013**: System MUST write results in a human-readable report and in a machine-readable format using stable metric names and units.
- **FR-014**: Each result MUST record the warehouse definition and scenario used, including a way to confirm their exact content, along with the seed, software version, and measurement window.
- **FR-015**: System MUST write a per-order record containing the order's arrival, start, and completion times, assigned crane, and final outcome.
- **FR-016**: System MUST record the modeling assumptions and simplifications that apply to a run in its report.

### Key Entities

- **Warehouse Definition**: The complete description of one warehouse variant; contains aisles, storage locations, transfer points, cranes, and the storage location rule.
- **Storage Location**: A storage cell that holds one load unit, identified by aisle, rack side, bay, and level; has a height, length, width, and position, and is either free or occupied.
- **Load Unit**: The unit moved by one order: a package of wood panels or a stack of paper on a pallet.
- **Crane**: Storage/retrieval equipment assigned to an aisle, with speed, acceleration, and handling parameters; performs one order at a time.
- **Transfer Point**: The place at either end of an aisle where load units enter it (inbound) or leave it (outbound).
- **Article**: A type of stored goods referred to by stock and orders.
- **Scenario**: Either generation parameters plus a seed, or an explicit order list, together with the simulated duration and warm-up period.
- **Order**: A request to store or retrieve one load unit, with an arrival time and final outcome.
- **Simulation Run**: One execution of a warehouse definition and scenario; records the seed, software version, and measurement window.
- **Run Result**: The metrics, per-order records, input identification, and modeling assumptions produced by a run.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A planner can go from a sample warehouse and scenario to a complete report using a single start action, with no graphical interface.
- **SC-002**: In 10 repeated runs of the same inputs and seed, including runs on differently loaded machines, 100% of reported metrics are identical.
- **SC-003**: In verification scenarios with hand-calculated results, order completion times and throughput deviate from the calculated values by no more than 0.1%.
- **SC-004**: A warehouse with 20 aisles and 100,000 storage locations can simulate 24 hours of operation at 1,000 orders per hour in under 60 seconds on a typical desktop computer.
- **SC-005**: Changing warehouse dimensions, equipment parameters, or the storage location rule requires editing data only, with no software change.
- **SC-006**: Each invalid sample input in the validation test set is rejected before simulation starts, with a message identifying the location of every seeded error.
- **SC-007**: For any reported number, a planner can identify its definition, unit, and source inputs from the run's outputs alone.

## Assumptions

- Users are warehouse planners or engineers who are comfortable editing structured data files and starting a program from a command line or script.
- Each aisle has one crane, and each crane handles one load at a time and completes one order per cycle. Dual-command cycles, multi-load handling, and cranes changing aisles are out of scope for this feature.
- Each aisle has racks on both sides, and its crane reaches both sides. All transfer points are at ground level, and each aisle end has at most one inbound and one outbound transfer point.
- Sample warehouses use an inbound transfer point at the left end and an outbound transfer point at the right end of each aisle, unless they are defined otherwise.
- Load units are always available at every inbound transfer point, and retrieved load units are removed immediately from outbound transfer points, so transfer points never block a crane. An order is not tied to a specific transfer point.
- A crane has no fixed home position: it waits where it finished its last order, so it travels empty from there to start the next one.
- Orders are dispatched first-come, first-served, and retrievals take the oldest stock of the requested article first. The storage location rules do not consider how busy each crane is.
- All cells within one warehouse definition have the same dimensions, every load unit fits every cell, and each cell holds one load unit. Load unit dimensions are not checked against cells. Double-deep storage is out of scope.
- Crane speed and acceleration do not depend on the weight of the load unit.
- Equipment failures, maintenance, staffing, and energy use are not modeled.
- Time is simulated, so results do not depend on real time or on the speed of the machine running them.
- The 3D visualization and live data connections are out of scope and will be separate features. Live warehouse systems are not needed for this feature.
- Scale and performance values in SC-004 are initial planning targets, because no specific warehouse has been named yet.
- Cost, payback, and automatic optimization of warehouse designs are out of scope.
