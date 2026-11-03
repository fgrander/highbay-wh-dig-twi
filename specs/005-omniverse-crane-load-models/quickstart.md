# Quickstart: Omniverse Crane and Load Models

Validation scenarios for this feature. Run all commands from the repository root in PowerShell. Commands and data are defined in [contracts/](contracts/) and [data-model.md](data-model.md).

## Prerequisites

The same as for [feature 004](../004-omniverse-run-replay/quickstart.md), including the three sample runs in `out/`.

## S1: Everything else is unchanged (SC-008, FR-016)

```text
uv run pytest
uv run pytest -m omniverse
```

All pass. Reference results differ from those before this feature only in the software version.

## S2: A realistic crane (User Story 1, SC-001, SC-003)

```text
powershell -ExecutionPolicy Bypass -File omniverse/run-replay.ps1 out/small
```

- Each crane has two columns joined at the top, with the load space between them.
- Play: cranes travel and lift, and the color of their columns shows their activity.
- Click on a column, the carriage, and the forks: each selects the crane. Click through the opening between the columns: what lies behind is selected.

Automated: crane positions at 100 sampled times in `out/small` and `out/small-stepped`, and clicks at 20 sampled points.

## S3: Seeing into a full aisle (SC-004)

Open `out/overloaded`, move to a time with a full warehouse, and look along an aisle from its end. The crane and its activity can be told apart for each of the four activities. A reviewer checks sample images, such as those in [images/](images/).

## S4: Forks at work (User Story 2, SC-002)

Open `out/small`, pause, and select a crane. Find a retrieval, which picks at a cell, and a storage, which sets at one. Use the time slider to move through its 12 seconds of handling, in both directions.

| Time in the step | Pick | Set |
|---|---|---|
| Start | Forks at rest, load in cell | Forks at rest, load on them |
| 40% | Forks extended under the load, towards its rack | Forks and load extended, load at its cell |
| 60% | Same | Forks extended, load at its cell |
| End | Forks at rest, load on them | Forks at rest, load in cell |

Repeat for the other rack. The figures do not change at any point before the recorded event at the end. Picks and sets at aisle ends show no fork movement.

Automated: both directions in Kit, and the fork function without Kit.

## S5: Loads and stacks (User Story 3, SC-005, SC-009)

```text
uv run highbay-sim run samples/replay/real-size-warehouse.yaml samples/replay/real-size-scenario.yaml --output out/real-size --replay
powershell -ExecutionPolicy Bypass -File omniverse/run-replay.ps1 out/real-size
```

Zoom in on a cell of each article, and on a crane carrying a load.

- `paper-5610` shows one wooden pallet with paper, as a shiny, banded block, over both fork sections.
- `board-5600` shows one stack of boards, one by one.
- `board-2100-3500` and `board-3000-2600` show two parts with a visible cut, in different places, each above its section, in the cell and on the crane.
- Details of a selected load name its article and its unit or parts.

Then copy `omniverse/exts/highbay.replay/data/load_definitions.toml`, change a `count`, and start with `-LoadDefinitions` and the copy. The stack changes, with no change to any code, in under 5 minutes.

## S6: Warnings (FR-013)

Each of these opens the run, and the window names the problem:

- Remove the line for `paper-5610` from a copy of the definitions: its loads show as a simple box in its color.
- Name a type that does not exist: that unit shows as a simple box.
- Point a `file` type at a missing file: that unit shows as a simple box.
- Set a split's lengths to 1.0 and 4.6: it shows as defined, and the warning names the lengths.
- Open `out/small` with a load 5.6 m long: it shows as defined, overlapping its neighbor.
- Give a definitions path that does not exist: all articles look simple.

## S7: Simple shapes (FR-017)

```text
powershell -ExecutionPolicy Bypass -File omniverse/run-replay.ps1 out/small --/exts/highbay.replay/models=simple
```

The scene is that of feature 004, with no forks or aisle lights.

## S8: Performance (SC-006, SC-007)

```text
uv run pytest tests/performance/test_omniverse_performance.py -m omniverse -s
```

The small sample reaches at least 30 frames per second, the warehouse with 100,000 cells at least 10, and it opens in under 5 minutes, all with detailed models.
