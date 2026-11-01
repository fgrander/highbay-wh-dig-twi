# Data Model: 3D Run Replay

Units are metres and seconds. Entities from the simulation are defined in `specs/001-headless-throughput-sim/data-model.md`. The file format is in [contracts/replay-format.md](contracts/replay-format.md).

## Replay Data

| Part | Content |
|---|---|
| `format_version` | Format version of the file; this feature uses 1 |
| `run` | The same identification as `result.json`: software version, seed, warehouse and scenario names and hashes, duration, and measurement window |
| `warehouse` | Layout, crane parameters, transfer points for each aisle, and each crane's start position |
| `articles` | Article IDs, referred to by index |
| `initial_stock` | Stored load units at the start of the run |
| `orders` | Per-order values, as in `orders.csv` |
| `events` | Time-ordered changes, as in the simulation's event stream |
| `reported` | The run's backlog, occupancy, and outcome metrics, plus the time of the backlog peak |

Validation by the viewer: the file can be read as JSON, `format_version` is supported, and all parts are present with their expected structure. Any failure shows a message and no partial state (FR-009).

## 3D layout

Calculated from the warehouse definition, for display only:

| Value | Calculation |
|---|---|
| x (along an aisle) | Simulation horizontal position. Left end is 0, right end is `bays × cell length`. |
| y (up) | Simulation vertical position |
| Aisle width | `cell width` |
| Block width | `racks_per_aisle × cell width + aisle width` |
| Block gap | `0.1 × cell width` |
| z of an aisle's center | `(aisle - 1) × (block width + block gap)` |
| z of rack 1 cell center | Aisle center `- (aisle width + cell width) / 2` |
| z of rack 2 cell center | Aisle center `+ (aisle width + cell width) / 2` |

A cell's box spans its bay's length, its level's height starting at its floor, and the cell width. A load unit is drawn inside it, slightly smaller than the cell.

## Crane position at a time

A movement has `start_s`, `end_s`, `start_position`, and `target_position`. For each axis with distance `d`, speed `v`, acceleration `a`, and elapsed time `t`:

| Phase | Distance travelled |
|---|---|
| Profile with full speed, `d >= v²/a`, while accelerating (`t < v/a`) | `a·t²/2` |
| At full speed (`v/a <= t < d/v`) | `v²/(2a) + v·(t - v/a)` |
| Braking (`d/v <= t < d/v + v/a`) | `d - a·(d/v + v/a - t)²/2` |
| Short distance, `d < v²/a`, with `T = 2·sqrt(d/a)`: first half | `a·t²/2` |
| Short distance: second half | `d - a·(T - t)²/2` |
| After the axis's own time | `d` |

The axis moves from start toward target by this distance. An axis finished early holds its target until `end_s`, which is the slower axis's time.

## Replay State

Derived only from replay data and a simulated time `t`, by applying all events with `time_s <= t`:

| Part | Derived from |
|---|---|
| Cell states and stored articles | `order_queued` reserves a cell, `load_set` stores in it, and `load_picked` frees it |
| Carried load unit of each crane | `load_picked` starts carrying and `load_set` ends it |
| Crane activity | The activity with `start_s <= t < end_s`, otherwise idle. Zero-length activities are never current. |
| Crane position | From the latest movement started at or before `t`, otherwise the crane's start position |
| Backlog in total | `order_arrived` adds one; `order_started` and `order_unfulfillable` remove one |
| Backlog per aisle | `order_queued` adds one for its aisle; `order_started` removes one |
| Waiting for a cell | `order_waiting_for_cell` adds one; `order_queued` of that order removes one |
| Occupancy | Cells holding a load unit, divided by all cells |
| Completed, unfulfillable, and arrived counts | The corresponding events |
| Warm-up or measurement window | `t` compared with the window start |

Total backlog always equals the sum of per-aisle backlog and orders waiting for a cell, once all events at a time have been applied.

Load units follow the spec's assumption: during a pick, a load unit stays where it is, and it moves to the crane at `load_picked`. During a set, it stays on the crane, and it moves to its cell or leaves at `load_set`.

## Cell display states

```text
free --> reserved_for_storage --> occupied --> reserved_for_retrieval --> free
```

Only `occupied` and `reserved_for_retrieval` cells draw a load unit, because only then is it physically there.

## Playback Session

| Field | Description | Rules |
|---|---|---|
| `time_s` | Current simulated time | Always within 0 and the run's duration |
| `playing` | Whether time is advancing | Stops at the end of the run |
| `speed` | Simulated seconds per real second | 1, 10, 60, 600, or 3,600 |
| Camera | Position and target | Never affects state or time |
| `selection` | Selected crane, cell, or load unit | Details are refreshed from the state at `time_s`. A selected load unit that no longer exists clears the selection. |

Initial values: time 0, paused, speed 60, default camera, no selection.
