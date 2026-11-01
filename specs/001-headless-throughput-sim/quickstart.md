# Quickstart: Validate the Headless Throughput Simulation

Each scenario below is a check that the feature works end to end. Formats are defined in [contracts/](contracts/).

## Prerequisites

- uv is installed
- From the repository root, `uv sync` completes successfully

## Scenario 1: Complete run (User Story 1)

```text
uv run highbay-sim validate samples/small-warehouse.yaml samples/daily-scenario.yaml
uv run highbay-sim run samples/small-warehouse.yaml samples/daily-scenario.yaml --output out/run-a
```

**Expected**: Both commands exit with code 0, with no display needed. `out/run-a` contains `report.md`, `result.json`, and `orders.csv`, and the report includes every metric in [results.md](contracts/results.md).

## Scenario 2: Reproducibility (FR-009, SC-002)

Run the same command again with `--output out/run-b`, then compare:

```text
git diff --no-index out/run-a out/run-b
```

**Expected**: No differences. Changing `seed` in a copy of the scenario changes `orders.csv` and the seed recorded in the report.

## Scenario 3: Hand-calculated verification (User Story 2, SC-003)

**Warehouse**: 1 aisle, 1 rack, 5 bays, 2 levels, with cells 4 m long and 3 m high. Horizontal speed is 2 m/s with acceleration of 1 m/s²; vertical speed is 1 m/s with acceleration of 1 m/s². Pick and set times are 10 s each. An inbound point is at the left end and an outbound point at the right end. All cells hold article `B`, except bay 3, level 2, which is free. The storage rule is `nearest_free`.

**Scenario**: 3,600 s, no warm-up, seed 1: store article `A` at 0 s, retrieve article `A` at 30 s.

**Geometry**: the free cell is at 10 m horizontally and 3 m vertically. Moving between that cell and either aisle end takes the longer of `10/2 + 2/1 = 7 s` and `3/1 + 1/1 = 4 s`, which is 7 s.

| Time (s) | Crane activity | |
|---|---|---|
| 0–10 | Pick at left end | Storage order starts at 0 |
| 10–17 | Move loaded to cell | |
| 17–27 | Set in cell | Storage order completes at 27 |
| 27–30 | Idle | |
| 30–40 | Pick from cell | Retrieval order starts at 30 |
| 40–47 | Move loaded to right end | |
| 47–57 | Set at right end | Retrieval order completes at 57 |

**Expected** results, all within 0.1%:

| Metric | Value |
|---|---|
| Throughput per hour | total 2, storage 1, retrieval 1 |
| Order cycle time | 27 s for both orders |
| Order waiting time | 0 s for both orders |
| Crane utilization shares | moving loaded 14/3600, moving empty 0, handling 40/3600, idle 3546/3600 |
| Occupancy | 9/10 at window start and at window end |

## Scenario 4: Invalid inputs (FR-004, SC-006)

```text
uv run highbay-sim validate samples/invalid/<case>-warehouse.yaml samples/daily-scenario.yaml
```

**Expected**: For each file in `samples/invalid/`, exit code 2, no simulation, and a message with the field path of each error. Cases include an aisle with no outbound point, a zero aisle count, a negative cell dimension, duplicate stock in one cell, stock in a location that does not exist, and a warm-up not shorter than the duration. A file with several errors reports all of them.

## Scenario 5: Warehouse variants (User Story 3, SC-005)

Run the same scenario against copies of the sample warehouse with one change each: a higher crane speed, a different `aisle_count`, a different cell size, and additional transfer points.

**Expected**: Every run succeeds with no software change. `result.json` has the same metric names and units in all runs. The higher-speed variant shows no increase in any order's crane travel time under the same assignments.

## Scenario 6: Edge cases (spec Edge Cases)

**Expected**, each covered by an automated test:

- A retrieval for an article with no stock is `unfulfillable` with reason `no_stock`, and the run continues.
- A storage order in a full warehouse waits for a free cell, and is `unfinished` if none becomes free.
- A scenario with no orders reports zero throughput, and its statistics are "not available".
- Orders still open at the end of the run are `unfinished` and are not counted as completed.

## Scenario 7: Performance (SC-004)

```text
uv run pytest tests/performance
```

**Expected**: 20 aisles, 100,000 cells, and 24 simulated hours at 1,000 orders per hour complete in under 60 seconds.

Note that this load may exceed the capacity of the tested cranes, which increases backlog but does not invalidate the timing check.
