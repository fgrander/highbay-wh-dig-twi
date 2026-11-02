# Research: Time-Stepped Plant Model

The project owner decided on a plant model that Omniverse will later display, per-axis positioning signals, and a controller limited to crane control. The other decisions are proposals made during planning.

## Default cycle time

- **Decision**: 50 ms by default, as a whole number of milliseconds from 1 to 1,000, chosen per run. The specification's initial value of 100 ms is replaced.
- **Rationale**: Each order has four steps that end on the next cycle boundary, on average half a cycle late, plus one cycle for the job handshake, so about 3 cycles per order. A crane that is always busy in the samples needs about 30 seconds per order. At 100 ms that is 0.3 seconds, or 1%, which is the limit of SC-004 with no margin. At 50 ms it is about 0.5%.
- **Alternatives considered**: 100 ms has no margin, and 10 ms costs five times the computing time for little gain.

## Performance

- **Decision**: Plain Python with slotted data classes, and no compiled or array-based code.
- **Rationale**: A prototype with 20 always-busy cranes, a controller state machine, and closed-form motion measured about 1.2 seconds per simulated hour at 50 ms, and 6.8 seconds at 10 ms, on the project owner's laptop. The prototype leaves out order handling and fault checks, but the 60-second limit leaves room for them.
- **Measured result**: The finished code needs 3.9 seconds with `nearest_free`, and 5.0 seconds with `random_free`, for one simulated hour at the planning target and 50 ms (SC-005), on the project owner's laptop with an AMD Ryzen 5 PRO 3500U.
- **Alternatives considered**: NumPy adds a dependency and makes per-crane logic harder to read, with no need for it.

## Time and motion

- **Decision**: Simulated time is `cycle * cycle_ms / 1000`. Motion is calculated from the start of the movement with the same profile as the event-based simulation, not added up step by step. Each axis ends on the first boundary at or after its exact end, where it takes exactly its target position.
- **Rationale**: Adding up steps accumulates rounding errors and can overshoot, which breaks FR-004. Calculating the position gives the same values as the viewer's profile, which is what SC-006 needs.
- **Alternatives considered**: Numerically integrating speed models nothing more, as the drives are ideal, and it adds errors.

## Signals

- **Decision**: Per-crane slotted data classes with three groups: job signals, commands, and status. Starts are triggered by a rising edge. The plant writes all status signals in every cycle from its own private state. Definitions are in [contracts/signal-list.md](contracts/signal-list.md), and a test checks them against the code.
- **Rationale**: Direct attributes are fast and easy to read. Keeping private state means that a controller writing to a status signal changes nothing in the plant. Rising edges match how PLC programs start positioning jobs, and a controller can hold a bit for any time.
- **Alternatives considered**: A dictionary of names to values is slower and has no type checks. Memory-mapped byte blocks suit a later PLC connection, but they belong to that feature, and they could be mapped from this list then.

## Job handshake

- **Decision**: Order handling writes a new `job_id` with source and destination. The controller writes the same number to `job_done_id` when finished, and order handling then issues the next job.
- **Rationale**: Comparing numbers costs one cycle per order and needs no separate acknowledge step. A bit-based request and acknowledge handshake takes two more cycles per order, which adds to the deviation for no benefit here.
- **Alternatives considered**: A job queue on the controller side would make controllers more complex, and would change which order is next.

## Observing what the plant does

- **Decision**: The plant reports started movements, handling, picks, and sets to the simulation's own run loop, which writes the existing events with the order of the current job. Controllers do not report these things.
- **Rationale**: A replaced controller cannot distort the results. Because the plant knows a movement's end when it starts, `end_s` is filled in as in event-based runs.
- **Consequence**: A movement outside a job is not counted as crane work, and a movement of zero distance creates no activity. Both are documented in the run's assumptions.
- **Alternatives considered**: Having the controller report job phases would make the results depend on the controller.

A pick or set counts for an order only if it happens at the place of that order's job, and an order completes only after its set has counted. A controller that reports a job done without doing it, or that puts a load elsewhere, therefore completes no order. The load stays where the plant put it.

## Shared order rules

- **Decision**: Move arrival handling, cell reservation, per-crane queues, orders waiting for a cell, the choice of aisle end, and final reasons from `engine.py` to `order_handling.py`. Before moving anything, record reference hashes of event-based results on the sample scenarios.
- **Rationale**: FR-013 requires the same rules in both modes, and SC-009 requires unchanged results. Reference hashes make the move safe. The software version is taken out before hashing, as it changes to 0.3.0.
- **Alternatives considered**: See the plan's complexity tracking.

## What SC-004 compares

- **Decision**: The 1% limit applies to `metrics.throughput_per_hour` (total, storage, and retrieval), with one completed order always allowed. The specification is changed to say this. `compare` also shows cycle time, waiting time, utilization, and backlog, without a limit.
- **Rationale**: In a short sample with about 120 completed orders, one order is already 0.85%, so whether one order finishes before the window ends must not fail the check. Waiting times and backlogs in an overloaded aisle add up small delays, and they can differ by more than 1% for a valid reason.

## Known sources of deviation from event-based runs

These are documented in the run's assumptions, as FR-023 requires:

1. Each movement and handling step ends on the next cycle boundary.
2. The job handshake takes one cycle per order.
3. An arrival takes effect at the next cycle boundary.
4. Because timing shifts slightly, an arrival and a released cell can swap order, which can change a chosen cell, especially with a random storage rule.

All four shrink as the cycle time shortens, apart from rare swaps.

Measured on the samples: throughput deviated by 0.00% on `small-warehouse` with `daily-scenario`, and on `overloaded-warehouse` with `busy-scenario`, each at 50 ms and 5 ms. The mean order cycle time deviated by +0.14% and +0.49% at 50 ms, and +0.05% at 5 ms on the overloaded sample. The estimate of about 3 cycles per order was therefore on the cautious side for throughput, because these samples complete the same orders in the measurement window. A sample with a crane that is busy until the end of the window could show a larger difference.

## Ordering within a cycle

- **Decision**: Order handling, then the controller reads and writes, then the plant advances by one cycle.
- **Rationale**: This fulfills the fixed sequence in FR-014, and the order is the same in every run. Order handling first means a controller sees a new job in the same cycle. Within order handling, completions come before arrivals, and arrivals are processed in their order of arrival.

## Faults

- **Decision**: A fault refuses the command and keeps the plant consistent. A movement already running finishes, because ideal drives have no modeled stopping distance. Further commands to that crane are ignored until a rising edge on `fault_reset`. Other cranes carry on. The built-in controller stops work on a crane with a fault and does not reset it, so the fault appears in the results.
- **Rationale**: Stopping a crane instantly at full speed would be physically wrong, and modeling braking is out of scope.
- **Alternatives considered**: Stopping the whole run would hide what the other cranes do, and it is not required.

## Choosing a controller

- **Decision**: `--controller FILE.py:CLASS` loads a class from a local Python file. By default, the built-in controller is used.
- **Rationale**: This satisfies FR-016 with the standard library only, and the file is one the user chose to run. The file's hash is recorded with the run, so results can be traced to it (Principle III).
- **Alternatives considered**: Python entry points need installation steps for a simple test controller.

## Compare command

- **Decision**: `highbay-sim compare A B` reads two `result.json` files and prints each metric, with its deviation. It writes no files, and it refuses results from different inputs.
- **Rationale**: FR-018 needs this directly, and today's manual comparison in the README is error-prone. Comparing different inputs would give misleading deviations.

## Signal record

- **Decision**: With `--record-signals`, every change is streamed to `signals.csv`, with the cycle, time, crane, signal, and value. It is checked after the controller has written and before the plant advances, when all signals show their values at the cycle's start.
- **Rationale**: Streaming keeps memory use low. Positions change in every cycle of a movement, so a long run at the planning target could reach about 100 MB per simulated hour. The quickstart recommends this for short runs, and the option is off by default.
- **Alternatives considered**: Rounding or thinning positions would no longer record every change, as FR-019 requires.

## Implementation notes

- **Intermittent failure from feature 002**: One test of 457 failed once on `main`, with its name not recorded. It did not appear again in T001 or in later full runs, so its cause remains unknown. Its name would be printed by `uv run pytest -q -rf`.
- **Test-first**: Tests for each logic module were run to completion and seen to fail before the code was written, as the plan requires. `tests/verification/` and `tests/data/reference_results.json` check finished behavior, and so passed from the start by design.
- **Built-in defects (T037)**: 24 defects were built in, one at a time. 19 were caught at once. Four of the others showed gaps that are now closed: a test for a load set at the wrong place could not fail, as its controller never reported the job done; picks at the wrong place, steps ending after the duration, and status signals written at rest were not covered. The last one, ending an axis one cycle later in `Plant`, changes nothing, as `axis_position` already returns the exact target at that time. The check remains for times within the rounding margin.
- **Changes from the plan**: `on_cycle` and the signal record run before the plant advances, so that all recorded values belong to the same time. `pick_finished` and `set_finished` also report the place, for the check above.
