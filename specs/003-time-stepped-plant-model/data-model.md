# Data Model: Time-Stepped Plant Model

Existing input files, `Allocation`, `OrderRecord`, `SimulationEvent`, and `RunRecord` are unchanged. Signal definitions are in [contracts/signal-list.md](contracts/signal-list.md).

## Cycle

One pass through this fixed sequence at time `t = cycle * cycle_ms / 1000`, starting with cycle 0:

1. **Order handling** reads `job_done_id` of each crane, completes finished orders, assigns any waiting orders, processes arrivals up to `t`, and writes new jobs to idle cranes.
2. **Controller** reads all signals and writes commands and `job_done_id`.
3. **Signal record**, if switched on, writes the changes. All signals now show their values at `t`.
4. **Plant** applies commands at time `t`, advances to `t + cycle`, and writes all status signals.

The run ends after the last cycle whose start is at or before the scenario's duration. Arrivals between that cycle's start and the duration are still processed, as they would be in an event-based run. Orders still open are reported with the same reasons as in an event-based run.

## Plant state

The plant keeps this state privately, and copies what signals show into the status signals in every cycle.

| Item | Content |
|---|---|
| Crane | Aisle, two axes, handling state, load on the crane or none, fault or none, last values of the rising-edge commands |
| Axis | Actual position, target, speed and acceleration limits, start cycle, end cycle. At rest when the current cycle has reached the end cycle. |
| Cells | Article of the load unit in each occupied cell, starting from `initial_stock` |
| Inbound points | Load unit offered at each inbound aisle end, or none |

The crane starts at the first inbound aisle end, as in event-based runs.

## Position to place

A command's place is found from the crane's actual position and the `side` signal, within 1 mm:

| Position | Place |
|---|---|
| Horizontal at a bay center, vertical at a level floor | The cell in rack `side` at this bay and level |
| Horizontal at an aisle end, vertical 0 | That aisle end, with its roles from the warehouse definition; `side` is ignored |
| Anything else | No place, which gives the fault `no_place` |

## Crane behavior

```text
              start axis                     all axes at rest
   at rest ---------------------> moving --------------------> at rest
      |
      | pick or set start, valid
      v
   handling  --- pick_time_s or set_time_s elapsed ---> at rest, load moved
```

- A pick moves the load unit from its place to the crane when handling ends. A set moves it from the crane to its place when handling ends. This matches when event-based runs release and fill a cell.
- A load unit set at an outbound aisle end leaves the warehouse.
- Handling ends on the first boundary at or after its exact end.

## Faults

The plant checks a command in the cycle of its rising edge. If it fails, the command has no effect, `fault_code` is set, and the fault is recorded with its cycle, time, crane, code, and description. While a fault is active, other commands to this crane are ignored. A rising edge on `fault_reset` clears it. A running movement finishes. A running handling step cannot fail after it starts.

Fault codes are listed in [contracts/signal-list.md](contracts/signal-list.md). An active fault's effect ends with the crane: no other crane is affected.

## Order handling

Moved from `engine.py`, with unchanged rules:

- An order receives its cell on arrival, and joins that aisle's first-come, first-served queue.
- A storage order with no free cell waits, and is assigned when a cell is released.
- A retrieval with no stock is unfulfillable.
- The aisle end is chosen when an order starts, with the lowest travel time. The left end wins a tie.

Added for this mode:

| Step | Effect |
|---|---|
| Crane idle and queue not empty | Order starts, `order_started` is written, the load unit is offered if it is a storage order, and a transport job is written |
| `job_done_id` equals the current `job_id` | `order_completed` is written. The next order can start in the same cycle. |

A job's source and destination use positions and `side`, so that a controller needs no warehouse data. A storage job goes from an inbound end to a cell, and a retrieval job from a cell to an outbound end.

## From plant observations to events

| Plant observation | Event |
|---|---|
| Movement started | `activity_started`: `moving_loaded` if a load is on the crane, otherwise `moving_empty`, with start position, target position, and `end_s` |
| Handling started | `activity_started`: `handling`, with `end_s` |
| Pick finished | `load_picked`, and a cell is released in `Allocation` |
| Set finished | `load_set`, and the cell is stored in `Allocation` |

Observations are written with the crane's current order. With no current order, as with a movement outside a job, no event is written. A pick or set counts only at the place of the current job, and only once per job. An order completes only when `job_done_id` equals its `job_id` and its set has counted.

## Validation

| Item | Rule |
|---|---|
| `cycle_ms` | Whole number from 1 to 1,000 |
| Controller | File exists, the class exists, and it can be created and has a `scan` method. Otherwise the run is refused before it starts. |
| A controller that raises an error | The run stops with exit code 1, and no result files are written |

## Controller interface

A controller has one required method, called once per cycle:

```python
class Controller(Protocol):
    def scan(self, signals: Mapping[int, CraneSignals]) -> None: ...
```

A controller is created with no arguments, and it receives no clock, plant, or warehouse data. The built-in controller goes through these states per crane: idle, to source, picking, to destination, setting, then writing `job_done_id` and back to idle.
