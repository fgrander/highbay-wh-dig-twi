# Contract: Signal List

**Signal list version**: 1

This is the only exchange between a controller and the plant (FR-007), and it is what a later PLC connection builds on. It does not depend on any PLC vendor. Each crane has its own set of these signals, so the definition is the same for any number of aisles (FR-010). A test checks this list against the code.

- A rising edge is a change from false to true between two cycles. A controller can hold the signal for any time, and it must be false for at least one cycle before the next edge.
- Positions are measured along the aisle (horizontal) from the left end, and upwards from the floor (vertical).

## From order handling to the controller

| Signal | Type | Unit | Meaning |
|---|---|---|---|
| `job_id` | integer | | Number of the current transport job, or 0 if none has been issued. A new number means a new job. |
| `source_horizontal_m` | number | m | Horizontal position to pick from |
| `source_vertical_m` | number | m | Vertical position to pick from |
| `source_side` | integer | | Rack to pick from: 1 or 2. Ignored at an aisle end. |
| `destination_horizontal_m` | number | m | Horizontal position to set at |
| `destination_vertical_m` | number | m | Vertical position to set at |
| `destination_side` | integer | | Rack to set at: 1 or 2. Ignored at an aisle end. |

## From the controller to order handling

| Signal | Type | Unit | Meaning |
|---|---|---|---|
| `job_done_id` | integer | | Number of the last finished job |

## From the controller to the plant

| Signal | Type | Unit | Meaning |
|---|---|---|---|
| `horizontal_target_m` | number | m | Target position of the horizontal axis |
| `vertical_target_m` | number | m | Target position of the vertical axis |
| `horizontal_start` | boolean, rising edge | | Starts the horizontal axis towards its target |
| `vertical_start` | boolean, rising edge | | Starts the vertical axis towards its target |
| `side` | integer | | Rack for handling: 1 or 2 |
| `pick_start` | boolean, rising edge | | Takes a load unit at the current position |
| `set_start` | boolean, rising edge | | Puts down the load unit at the current position |
| `fault_reset` | boolean, rising edge | | Clears an active fault |

## From the plant to the controller

| Signal | Type | Unit | Meaning |
|---|---|---|---|
| `horizontal_actual_m` | number | m | Actual position of the horizontal axis |
| `vertical_actual_m` | number | m | Actual position of the vertical axis |
| `horizontal_in_position` | boolean | | The horizontal axis is at rest |
| `vertical_in_position` | boolean | | The vertical axis is at rest |
| `handling_active` | boolean | | A pick or set is running |
| `load_present` | boolean | | A load unit is on the crane |
| `fault_code` | integer | | The active fault, or 0 if none |

## Fault codes

| Code | Name | Meaning |
|---|---|---|
| 0 | `none` | No active fault |
| 1 | `target_out_of_range` | An axis target is outside the aisle's range of travel |
| 2 | `crane_busy` | A start arrived while an axis was moving or handling was running |
| 3 | `no_place` | Handling was started at a position that is neither a cell nor an aisle end |
| 4 | `invalid_side` | Handling at a cell used a side other than an existing rack |
| 5 | `nothing_to_pick` | The place holds no load unit, or the aisle end has no inbound role |
| 6 | `place_occupied` | The cell already holds a load unit |
| 7 | `set_not_allowed` | The aisle end has no outbound role |
| 8 | `crane_already_loaded` | A pick started while a load unit was on the crane |
| 9 | `crane_empty` | A set started with no load unit on the crane |
| 10 | `conflicting_commands` | Pick and set were both started in the same cycle |

## Timing

- In a cycle, a controller sees status as of the start of that cycle.
- Commands take effect at that time, and their results appear in the next cycle's status.
- Both axes started in the same cycle form one movement. Each axis follows its own speed and acceleration, and may reach its target at a different time.
- An axis started while the other is moving gives the fault `crane_busy`. A later version of this list could allow overlapping movements.

## Changes

Any change to a signal's name, type, unit, or meaning requires a new version number, and the version is recorded with each run.
