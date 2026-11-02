# Data Model: Omniverse Run Replay

The input is `replay.json`, unchanged, as defined in [the replay format](../002-3d-run-replay/contracts/replay-format.md). State rules follow [the 3D replay's data model](../002-3d-run-replay/data-model.md). This file describes only what this feature adds.

## Warehouse description

What a state source gives once, before any state.

| Field | Meaning |
|---|---|
| `layout` | Aisles, racks, bays, levels, and cell dimensions |
| `crane` | Axis speeds and accelerations, and handling times |
| `transfer_points` | Roles at each aisle end |
| `crane_start_positions` | Start position per aisle |
| `articles` | Article names, in the order that decides their colors |
| `run` | Identification, duration, and measurement window, where known |
| `reported` | Reported values, where known. A live source has none. |

## Run state

What is true at one simulated time.

| Field | Meaning |
|---|---|
| `time_s` | The simulated time of this state |
| `in_measurement_window` | Whether the time is within the measurement window |
| `backlog` | Total, per aisle, and orders waiting for a cell |
| `occupied_cells`, `occupancy` | Stored load units, as a count and a share of all cells |
| `completed`, `arrived`, `unfulfillable` | Order counts so far |
| `cranes` | For each aisle: position, activity, order, and carried load unit |

Details for a selected cell or load unit are given on request: location, cell state, article, and the order that stored or will retrieve the load unit.

### Rules

- The state for a time depends only on that time and the source's data (FR-005).
- Reaching a time by playing, or by moving forward or backward, gives the same state.
- Time stays within the source's available range.
- Cell states are `free`, `occupied`, `reserved_for_storage`, and `reserved_for_retrieval`, as in the browser viewer. Reservations change no instance.

## Scene

| Prim path | Type | Content |
|---|---|---|
| `/World/Floor` | Cube | Below the warehouse |
| `/World/Dome`, `/World/Sun` | Lights | Fixed lighting |
| `/World/Racks` | PointInstancer | Uprights and beams |
| `/World/Loads` | PointInstancer | One instance per cell, one prototype per article color |
| `/World/Cranes/Aisle_<n>` | Xform | Moves along the aisle, with a mast |
| `/World/Cranes/Aisle_<n>/Carriage` | Xform | Moves up the mast, with its carried load unit |
| `/World/TransferPoints/Aisle_<n>_<end>_<role>` | Cube | Marker at an aisle end, with the role's color |
| `/World/Camera` | Camera | The default view |
| `/World/Selection` | Xform | Outline at the selected object, hidden with no selection |

Sizes and positions follow `layout.js`, with x along the aisle, y up, and z across aisles.

### Instance rules

- The instance number of a cell is fixed, and follows from aisle, rack, bay, and level: `(aisle-1, rack-1, bay-1, level-1)` in mixed-radix form.
- A cell that holds a load unit is visible, with the prototype of its article's color. All other cells are in `invisibleIds`.
- A load unit on a crane is drawn by the crane's own carried load, not by an instance.
- Only changed cells cause an instance update. Moving backward rewrites all instances once.

### Color rules

- Article colors: a fixed sequence, in `articles` order, repeating after eight colors, the same as `appearance.js`.
- Crane colors by activity: moving empty is blue, moving loaded is orange, handling is purple, and idle is gray, the same as `appearance.js`.

### Scene identity

The scene built before the first state update has no timestamps or machine details, so that identical data and software give an identical scene (FR-016). A test compares the exported text of two builds.
