# Feature Specification: Omniverse Crane and Load Models

**Feature Branch**: `005-omniverse-crane-load-models`

**Created**: 2026-11-03

**Status**: Draft

**Input**: User description: "Detailed crane and load models in the Omniverse replay. The stacker crane has two columns with the load between them, and two fork sections that extend across the aisle towards either rack. Every transport carries a pair of load units, one on each section, always picked, moved, and set together, in one cell. A pair is one article to the simulation, so a retrieval order always asks for a specific pair. The two load units of a pair can differ, for example a stack of particle boards and a pallet with a stack of about 1000 sheets of laminated paper, and a mapping per article decides what each of the two looks like. In the replay, both fork sections extend together during the recorded handling time, towards the rack of the cell, and the pair moves with them. The simulation, its results, the recording format, and the browser replay do not change. Selecting works on the visible crane, and aisles get enough light to see the crane. Real dimensions are not available yet, so all dimensions are placeholders that can be changed. Out of scope: separate movement of the two sections in the simulation, transports with a single load unit, pairs from different cells, PLC connection, live data, manufacturer CAD data."

## Clarifications

### Session 2026-11-03

- Q: What is the second load type? → A: A pallet with paper, not a Malette. The paper is 5.61 m long and 2.08 m wide, and its long side runs along the aisle.
- Q: How many paper pallets are in a cell? → A: One.
- Q: What does the paper lie on? → A: On a base board 30 mm thick.
- Q: What are the particle boards' sizes? → A: At most 5.6 m by 2.07 m. A stack can be split in two, not necessarily in the middle. The smallest part is 1.5 m long, and the parts add up to 5.6 m.
- This replaces the earlier assumption that each transport carries two load units of any kind side by side. A cell holds a load of either one whole unit, on both fork sections, or two parts of a split board stack, one on each. Paper and boards cannot share a cell, as each of them fills its length.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See a Realistic Crane at Work (Priority: P1)

A planner opens a recorded run in the Omniverse application and sees a stacker crane with two columns, with the load between them, moving along its aisle. They can see the crane inside a full aisle, tell what it is doing, and select it by clicking on any visible part.

**Why this priority**: The crane is the main moving object in the warehouse. A crane that looks right and can be seen at work is useful alone, without any change to the load units.

**Independent Test**: Can be fully tested by opening a sample run, viewing a crane in a full aisle, comparing its position over time with the recording, and clicking on each of its main parts.

**Acceptance Scenarios**:

1. **Given** a recorded run, **When** the planner opens it, **Then** each crane has two columns, one on either side of its load space, joined at the top, with a carriage and two fork sections that move up and down between the columns.
2. **Given** a full warehouse, **When** the planner looks along an aisle, **Then** the crane in that aisle can be seen and its activity can be told apart by color.
3. **Given** a playing run, **When** the crane moves, **Then** its travel and lift positions are the ones recorded.
4. **Given** an open run, **When** the planner clicks on a column, the carriage, or the forks of a crane, **Then** that crane is selected.
5. **Given** the lowest storage level, **When** a load is handled there, **Then** no part of the load passes through a part of the crane.

---

### User Story 2 - See the Forks Handle Loads (Priority: P2)

While a crane picks or sets at a cell, both fork sections extend together towards the rack of that cell and return. The load travels on them, so that the planner can see the transfer between crane and rack.

**Why this priority**: This is the behavior that sets the real crane apart, and it makes each handling step readable. It builds on the crane from User Story 1.

**Independent Test**: Can be fully tested by moving through one recorded pick and one recorded set in each rack, and comparing fork positions and load unit positions with the times in the recording.

**Acceptance Scenarios**:

1. **Given** a recorded pick at a cell in either rack, **When** the planner moves through its handling time, **Then** both sections extend towards that rack, the load moves onto them from the cell, and both return with it.
2. **Given** a recorded set, **When** the planner moves through its handling time, **Then** both sections extend with the load, the load stays in the cell, and both return empty.
3. **Given** any time in a handling step, **When** the planner reaches it by playing or by moving forward or backward, **Then** forks and load look the same.
4. **Given** a time outside a handling step at a cell, **When** it is shown, **Then** both sections are at rest in the crane.
5. **Given** any handling step, **When** it is shown, **Then** the figures and details shown are the same as those of the recording, whatever the animation shows.

---

### User Story 3 - See What Is Stored (Priority: P3)

Each stored or carried load shows what it is: a pallet with paper, a whole stack of particle boards, or a stack split in two parts. The planner defines this per article.

**Why this priority**: It makes the warehouse look like the real one, and it shows the mix of stock at a glance. Cranes and forks are useful without it.

**Independent Test**: Can be fully tested by defining articles of each kind, opening a run with them, and checking that each cell and carried load shows what is defined for its article.

**Acceptance Scenarios**:

1. **Given** a definition of an article, **When** a run with that article is opened, **Then** each of its stored and carried loads shows the unit or the two parts defined.
2. **Given** a stack split in two parts of different lengths, **When** it is shown in a cell and on a crane, **Then** each part keeps its length and its side, and the cut can be seen.
3. **Given** the load unit types provided, **When** the planner views them, **Then** a stack of particle boards shows its individual boards, and a paper pallet looks like a base board with a compact stack of laminated, slightly shiny sheets on it.
4. **Given** an article with no definition, **When** a run is opened, **Then** its loads show as a simple load unit in its article color, and a warning names the article.

### Edge Cases

- A run has more articles than definitions: undefined articles show simply, and every one is named once in a warning.
- A definition names a load unit type or file that cannot be found: the simple look is used, and a warning names it. The run still opens.
- A load does not fit in its cell: it shows as defined, and a warning names the article and the size.
- The two parts of a split stack are shorter than the smallest part, or do not add up to the stack's length: they show as defined, and a warning names the article and the lengths.
- A warehouse has one rack per aisle: the forks only ever extend towards that rack.
- A handling step takes place at an aisle end, where no rack exists: the forks stay at rest, and the load appears or leaves at the recorded moment.
- A handling step is very short or playback is very fast: fork positions are correct at each shown time, even if the movement cannot be seen.
- The state source is not a recording and gives no handling details: the forks stay at rest, and everything else works.
- The camera is close to the crane at the lowest level: parts may touch the floor plate only as far as the placeholder dimensions allow, as listed in the assumptions.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Each crane MUST show two columns, one on either side of the load space along the aisle, joined at the top, with travel gear below each column, a carriage, and two fork sections.
- **FR-002**: Crane models MUST be generated from the warehouse's dimensions, so that any warehouse has a crane of the right height and width.
- **FR-003**: Crane parts MUST follow the recorded travel and lift positions within the 1 cm tolerance of the existing replay.
- **FR-004**: The crane MUST keep showing its activity with the existing activity colors.
- **FR-005**: Clicking on any visible part of a crane MUST select that crane, and selection boxes MUST match the crane as shown.
- **FR-006**: During a handling step at a cell, both fork sections MUST extend together towards the rack of that cell, and return, within the recorded handling time.
- **FR-007**: A picked load MUST move from its cell onto the forks during the handling step, and a set load MUST move from the forks into its cell.
- **FR-008**: Fork and load positions MUST depend only on the simulated time and the recorded data, however that time was reached.
- **FR-009**: The two fork sections MUST be separate, individually movable parts of the model, although this feature always moves them together.
- **FR-010**: A load MUST show as one whole unit over both fork sections, or as two parts side by side along the aisle, with one part above each section.
- **FR-011**: Users MUST be able to define per article, in versionable data, which unit its load is, or which two parts, with their lengths.
- **FR-012**: At least a stack of particle boards, which can be split, and a pallet with about 1000 laminated sheets MUST be provided as load unit types, with their sizes as changeable values and the sizes in the clarifications as defaults.
- **FR-013**: Undefined articles, types that cannot be found, loads that do not fit in a cell, and splits against a type's limits MUST lead to a warning that names them, and MUST NOT stop a run from opening.
- **FR-014**: Aisles MUST be lit well enough to see a crane in a full aisle.
- **FR-015**: Details of a selected load MUST name the article and its unit or two parts, with their lengths.
- **FR-016**: The simulation, its results, the recording format, the browser replay, and all existing metrics MUST stay unchanged, except for the recorded software version.
- **FR-017**: A warehouse MUST keep working in the application with the simple shapes when no detailed models are chosen.
- **FR-018**: Documentation MUST state that a load is one article and one order to the simulation, so that throughput figures count loads, and MUST state how to change all placeholder dimensions.

### Key Entities

- **Crane Model**: The two columns, travel gear, top beam, carriage, and two fork sections of one crane, sized from a warehouse.
- **Fork Section**: One of two parts of the forks that can extend across the aisle towards either rack. Always moved together in this feature.
- **Load**: What one cell holds and one transport carries: one whole unit, or two parts of a split stack. It is one load unit and one article to the simulation.
- **Load Unit Type**: The look and size of one unit, such as a stack of particle boards or a pallet of laminated paper.
- **Load Definition**: For one article, its unit, or its two parts with their lengths.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: At 100 sampled times in recordings from both simulation modes, crane parts deviate by no more than 1 cm from the recorded positions.
- **SC-002**: In one recorded pick and one recorded set per rack, forks are at rest at the start and end of the handling time and fully extended in between, and moving to the same time forward and backward shows the same positions.
- **SC-003**: Clicks at 20 sampled visible points on a crane's columns, carriage, and forks select that crane every time.
- **SC-004**: In a view along a full aisle, a reviewer can identify the crane and each of the four activities in 100% of a set of sample images.
- **SC-005**: A reviewer can tell apart a particle board stack and a paper pallet in a default view of a cell and in a close view, in 100% of a set of sample images.
- **SC-006**: The small sample warehouse with all detailed models plays at 30 frames per second or more, and the warehouse with 100,000 storage locations at 10 frames per second or more, on the reference computer at a resolution of 1920×1080.
- **SC-007**: A warehouse with 100,000 storage locations with all detailed models opens in under 5 minutes.
- **SC-008**: Result files for all sample scenarios stay byte-identical to those from before this feature, except for the recorded software version, and all existing tests pass.
- **SC-009**: A person can change a stack's size or a load definition, and see the result in the application, in under 5 minutes, with no change to any program code.

## Assumptions

- The project owner confirmed that all of a cell's load moves together, in one transport, and that an order always asks for a specific load. A load, whole or split, is therefore one article to the simulation, and throughput counts loads. The project owner confirmed that both parts of a split stack are always stored and retrieved together. Other cases would need a change to the simulation, as a separate feature.
- The project owner confirmed the crane's form: two columns with the load between them, and two fork sections that can move in both directions across the aisle. Moving them separately is prepared in the model, but no recorded data calls for it.
- The lengths and widths of paper and boards are real values from the project owner. The base board's 30 mm is real as well. Other heights, cell sizes, and crane dimensions are placeholders: for example, particle boards 19 mm thick in a stack of 30, and sheets 0.3 mm thick in a stack of 1000. These real sizes do not fit the existing sample warehouses, whose cells are 3.2 m long and 1.5 m wide, so those samples keep smaller types, and a new sample warehouse has cells for the real sizes.
- As the sample warehouses have cells at floor level, everything below a load at the lowest level has to fit in very little height, which makes forks thin. Real dimensions may allow a higher lowest level and stronger forks.
- Handling times come from the recording. How they divide between extending, lifting, and returning is decided in the plan, for display only.
- During a handling step, the figures follow the recording. A load can look as if already on the forks while the recording still counts it in its cell until the step's recorded event. This is display only.
- Forks do not move at aisle ends, as the layout of transfer points is not defined yet.
- This feature builds on the Omniverse replay of feature 004, which is not merged yet.
- Individual sheets are not modeled, as this would need up to 100 million objects at the planning target. A stack's edge shows them as a surface pattern.
- The models are general, not those of a manufacturer. Bodies of real cranes, rails along the whole aisle, and safety equipment are not part of this feature.
