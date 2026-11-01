# Quickstart: Validate the 3D Run Replay

Each scenario checks that the feature works end to end. Formats and behavior are defined in [contracts/](contracts/).

## Prerequisites

- `uv sync` completes successfully
- For automated viewer tests only: `uv run playwright install chromium`
- For viewing: a current Chromium-based browser or Firefox

## Scenario 1: Watch a replay (User Story 1, SC-001)

```text
uv run highbay-sim run samples/small-warehouse.yaml samples/daily-scenario.yaml --output out/replay-a --replay
uv run highbay-sim view out/replay-a
```

**Expected**: The browser opens the viewer showing 4 aisles, 2 racks per aisle, 40 bays, 10 levels, and the initial stock. After pressing play, cranes move and load units appear on cranes and in cells. Pause, speed, restart, and the time slider all work.

Disconnect from the internet and repeat the view command. **Expected**: The viewer works the same.

## Scenario 2: Results are unchanged (FR-002, FR-003, SC-007)

```text
uv run highbay-sim run samples/small-warehouse.yaml samples/daily-scenario.yaml --output out/no-replay
uv run highbay-sim run samples/small-warehouse.yaml samples/daily-scenario.yaml --output out/replay-b --replay
git diff --no-index out/no-replay/result.json out/replay-b/result.json
git diff --no-index out/no-replay/report.md out/replay-b/report.md
git diff --no-index out/no-replay/orders.csv out/replay-b/orders.csv
git diff --no-index out/replay-a/replay.json out/replay-b/replay.json
```

**Expected**: No differences in any comparison. `out/no-replay` has no `replay.json`.

## Scenario 3: Hand-calculated crane positions (FR-011, SC-004)

Use `samples/verification/v1-warehouse.yaml` and `v1-scenario.yaml` from the simulation feature. Horizontal speed is 2 m/s with acceleration of 1 m/s². Vertical speed is 1 m/s with acceleration of 1 m/s². The storage order's loaded movement runs from (0, 0) at 10 s to (10, 3) at 17 s.

**Horizontal**: 2 s accelerating, 3 s at full speed, 2 s braking, over 10 m. **Vertical**: 1 s accelerating, 2 s at full speed, 1 s braking, over 3 m, so finished after 4 s, at 14 s.

**Expected** crane position, within 1 cm:

| Time (s) | Horizontal (m) | Vertical (m) | Note |
|---|---|---|---|
| 10.0 | 0.00 | 0.00 | Movement starts |
| 11.0 | 0.50 | 0.50 | Both accelerating |
| 12.0 | 2.00 | 1.50 | Horizontal at full speed from here |
| 13.0 | 4.00 | 2.50 | Vertical braking from here |
| 14.0 | 6.00 | 3.00 | Vertical finished |
| 15.0 | 8.00 | 3.00 | Horizontal braking from here |
| 16.0 | 9.50 | 3.00 | |
| 17.0 | 10.00 | 3.00 | Movement finished |

**Load units**: at 9.9 s, none is on the crane. At 10.0 s and 26.9 s, one is on the crane, and the cell is empty. At 27.0 s, it is in the cell at bay 3, level 2, and at 40.0 s it moves to the crane again. At 57.0 s, it is gone.

## Scenario 4: Jumping and playing agree (FR-012, SC-005)

**Expected**, covered by an automated test: for each of many times in a sample run, moving directly to the time, moving there backward from later, and reaching it through playback give identical crane positions, stored load units, and counts.

## Scenario 5: Navigation and inspection (User Story 2)

In the viewer from Scenario 1, at a time with a moving crane:

- Rotate, move, and zoom, then press the default view button. **Expected**: Simulated time is unaffected, and the whole warehouse is visible afterward.
- Select the moving crane. **Expected**: Its number, activity, order, and destination are shown.
- Select a stored load unit, then an empty cell. **Expected**: The details match `out/replay-a/orders.csv` for the same order and time.

## Scenario 6: Bottlenecks (User Story 3, SC-006, FR-020)

```text
uv run highbay-sim run samples/replay/overloaded-warehouse.yaml samples/replay/busy-scenario.yaml --output out/overloaded --replay
uv run highbay-sim view out/overloaded
```

**Expected**: Crane colors show their activity, with aisle 1 visibly busier. Figures show more backlog in aisle 1 than in the others. "Go to highest backlog" moves to a time where the displayed total equals `max_in_window` in `result.json`. At the end of the run, the displayed completed orders, backlog, and occupancy equal `report.md`.

## Scenario 7: Invalid replay files (FR-009)

Copy a replay file and make these changes: truncate it, set `format_version` to 999, and remove `events`. Open each with `highbay-sim view`.

**Expected**: Each shows a clear message and no warehouse. Running `highbay-sim view` with a path that does not exist gives exit code 2.

## Scenario 8: Edge cases (spec Edge Cases)

**Expected**, covered by automated tests: a run with no orders plays with counts at zero; orders unfinished at the end stop at the end of the run; unfulfillable orders move nothing and are counted; zero-length activities cause no gap; and the time always stays within the run.

## Scenario 9: Performance (SC-002, SC-003, SC-008)

```text
uv run pytest tests/performance
```

**Expected**: Writing replay data at the planning target adds at most 30 seconds, and the file is at most 100 MB. Moving to any time takes under 1 second.

**Manual check of frame rate**: Write the planning-target replay with `uv run python tests/performance/write_planning_target.py out/target`, then open it:

```text
uv run highbay-sim view out/target --no-browser
```

Open the printed address with `?benchmark=1` in a normal browser window. **Expected**: The displayed average is at least 30 frames per second on a typical desktop computer with 3D-capable graphics. Record the result and graphics hardware in the pull request or commit.
