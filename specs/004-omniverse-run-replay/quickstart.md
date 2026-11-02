# Quickstart: Omniverse Run Replay

Validation scenarios for this feature. Run all commands from the repository root in PowerShell. Commands and controls are defined in [contracts/](contracts/).

## Prerequisites

```text
uv sync
uv run playwright install chromium
omniverse/setup.ps1
uv run highbay-sim run samples/small-warehouse.yaml samples/daily-scenario.yaml --output out/small --replay
uv run highbay-sim run samples/small-warehouse.yaml samples/daily-scenario.yaml --output out/small-stepped --replay --time-stepped
uv run highbay-sim run samples/replay/overloaded-warehouse.yaml samples/replay/busy-scenario.yaml --output out/overloaded --replay
```

The Omniverse scenarios need an RTX graphics card. The first start compiles shaders and can take several minutes.

## S1: Everything works without Omniverse (SC-008)

On a computer without Kit, or with its folder renamed:

```text
uv run pytest
```

**Expected**: All tests pass, and tests that need Kit are reported as skipped. Reference hashes confirm that results are unchanged.

## S2: Logic matches the browser viewer (SC-002)

```text
uv run pytest tests/omniverse tests/viewer -k "omniverse or parity"
uv run --python 3.12 pytest tests/omniverse
```

**Expected**: At 100 sampled times from both simulation modes, crane positions differ by no more than 1 cm, and every load unit's location matches.

## S3: Replay a run (User Story 1, manual)

```text
omniverse/run-replay.ps1 out/small
```

**Expected**: Within 60 seconds on later starts, the warehouse appears with racks, cranes, stock, and transfer points in RTX rendering. Play, pause, restart, each speed, and the time slider work. Moving backward and forward to one time shows the same scene.

Repeat with `out/small-stepped`.

## S4: Close the application (manual)

Close the window from S3.

**Expected**: The window closes, `run-replay.ps1` returns within 30 seconds, and no `kit` process remains. See [research.md](research.md) for why this needs checking.

## S5: Understand a run (User Story 2, SC-006)

```text
omniverse/run-replay.ps1 out/overloaded
```

Choose **Go to highest backlog**. Click a crane, a load unit, and an empty cell.

**Expected**: The backlog shown equals `backlog_orders.max_in_window` in `result.json`, and the details match the browser viewer for the same selection at the same time.

## S6: Nothing is changed (FR-010)

Record file hashes of `out/small` before S3 and compare them afterwards.

**Expected**: Hashes are identical, and the folder has no new files.

## S7: Invalid recordings (FR-014)

Open a folder without `replay.json`, one with a damaged file, and one with a `format_version` of 999.

**Expected**: Each shows a message naming the file and problem, with no partial scene.

## S8: State interface and looks (User Story 3, SC-007)

```text
uv run pytest tests/omniverse_kit -m omniverse
```

**Expected**: A scripted source drives the scene with no change to scene or display code. A replacement look changes only the appearance, and a missing look gives a warning and the simple shape. Two scene builds from one recording are identical (FR-016).

## S9: Performance (SC-003, SC-004, SC-005)

```text
uv run pytest tests/performance -m omniverse
```

**Expected**: With the whole warehouse in view at 1920×1080, the small sample reaches 30 frames per second or more, and the planning target opens in under 5 minutes and reaches 10 frames per second or more. Moving to any time on the small sample takes under 1 second.

## S10: From a fresh checkout (SC-009, manual)

Follow the README on a fresh clone, starting from `omniverse/setup.ps1`, and time it.

**Expected**: S3 works within 60 minutes, including downloads.
