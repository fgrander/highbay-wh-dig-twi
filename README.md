# Highbay Warehouse Digital Twin

A command-line throughput simulation of one high-bay warehouse, written in Python. It runs with no graphical interface. A warehouse and an order scenario are defined in YAML files, and each run writes a report of throughput metrics.

A run can also be replayed in 3D in a web browser or in NVIDIA Omniverse, or carried out cycle by cycle by a plant model with a replaceable controller. PLC connections and live data are planned as later features.

## Installation

You need [uv](https://docs.astral.sh/uv/). From the repository root, run:

```text
uv sync
```

This creates the project's own environment with Python 3.14.

## Usage

Check the input files without simulating:

```text
uv run highbay-sim validate samples/small-warehouse.yaml samples/daily-scenario.yaml
```

Run a simulation:

```text
uv run highbay-sim run samples/small-warehouse.yaml samples/daily-scenario.yaml --output out/run-a
```

If invalid input is found, no simulation starts, and every problem is listed with its field path. Existing output files are only replaced if you add `--overwrite`.

Exit codes are 0 for success, 1 for a failure such as output that cannot be written, and 2 for invalid input or incorrect command usage.

All values in `samples/` are illustrative and are not real equipment data. Replace them with your own before drawing conclusions from the results.

## 3D replay

![Cranes working through a growing backlog in aisle 1, replayed at 60x speed](docs/media/replay.gif)

The recording shows `samples/replay/overloaded-warehouse.yaml` in the default view. All numbers in this sample are placeholders. See also the [default view](docs/media/default-view.png) and the [highest backlog with a crane selected](docs/media/peak-backlog.png).

Add `--replay` to write `replay.json` next to the results, then open it:

```text
uv run highbay-sim run samples/small-warehouse.yaml samples/daily-scenario.yaml --output out/run-a --replay
uv run highbay-sim view out/run-a
```

The viewer opens in your web browser and runs until you press Ctrl+C. It needs no internet connection, can only be reached from your own computer, and changes no files. Result files are identical with and without `--replay`. With `--overwrite` but without `--replay`, an existing `replay.json` is deleted, so that it can never be viewed with newer results.

| Control | Action |
|---|---|
| Play, Restart, time slider, Speed | Play the run, return to its start, move to any time, or change the speed from 1× to 3,600× |
| Drag, right-drag, scroll in the view | Rotate, move, or zoom |
| Default view | Show the whole warehouse again |
| Click | Select a crane, or the first load unit along that line, or otherwise a cell |
| Go to highest backlog | Move to the first moment of the reported maximum |

Crane colors show the current activity, and the side panel shows backlog per aisle and other figures. `samples/replay/` has a warehouse with an overloaded aisle to try this on.

The viewer is automatically tested in Chromium. It needs WebGL 2, and Firefox is expected to work but has not been verified.

Objects are simple shapes for now. To use detailed models, change `src/highbay_sim/viewer/appearance.js`, the only module that decides how objects look. See [the viewer contract](specs/002-3d-run-replay/contracts/viewer.md) for details.

## Omniverse replay

![A crane in a full aisle in Omniverse, with stacks of particle boards and paper pallets](docs/media/omniverse-loads.jpg)

A recorded run from either simulation mode can also be replayed in NVIDIA Omniverse with RTX rendering. It reads the same `replay.json` and changes no files. The simulation and the browser replay work without any of this.

You need Windows and an NVIDIA RTX graphics card. RTX 3070 or better is NVIDIA's recommendation, and this project has been measured on an RTX 3080 with 10 GB. The setup downloads several gigabytes.

Install Omniverse Kit outside the repository, by default in `C:\dev\omniverse\kit-app-template`:

```text
powershell -ExecutionPolicy Bypass -File omniverse/setup.ps1
```

Using Kit means accepting the [NVIDIA Software License Agreement](https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-software-license-agreement/) and the Product-Specific Terms for NVIDIA Omniverse. The script never accepts them for you: the first time, it stops and shows the command that asks you. Kit's anonymous data collection is switched off in this project's application.

Open a run:

```text
uv run highbay-sim run samples/replay/overloaded-warehouse.yaml samples/replay/busy-scenario.yaml --output out/overloaded --replay
powershell -ExecutionPolicy Bypass -File omniverse/run-replay.ps1 out/overloaded
```

The first start compiles shaders, which can take several minutes, and later starts take seconds. Close the window to end the application.

The **Highbay Replay** panel beside **Property** has the same controls, figures, and legend as the browser replay. A click in the view selects a crane, or the first load unit along that line, or otherwise a cell, and a click on empty space clears the selection. Kit's own controls move the camera. Kit's selection of objects in the view is switched off.

At 1920×1080 with the whole warehouse in view, and with Kit's frame limiter off, one measurement without a window with all detailed models gave 153 frames per second on the small sample and 20.9 on a warehouse with 100,000 cells, and 24.4 with nearly all of those cells filled. See [the research notes](specs/005-omniverse-crane-load-models/research.md) for the details and limits.

Cranes have two columns with the load between them, and two fork sections that extend during recorded handling. Each cell shows a paper pallet, or a whole or split stack of particle boards, as defined per article in a data file. To see this with the real load sizes:

```text
uv run highbay-sim run samples/replay/real-size-warehouse.yaml samples/replay/real-size-scenario.yaml --output out/real-size --replay
powershell -ExecutionPolicy Bypass -File omniverse/run-replay.ps1 out/real-size
```

To the simulation, a load is always one article and one order, whole or split, so throughput figures count loads. This is why result files keep saying that multi-load handling is not modeled. The cells, crane, and stack heights of that sample are placeholders, so its results say nothing about a real warehouse yet.

To change sizes, definitions, or models, see [the extension's notes](omniverse/exts/highbay.replay/README.md). To connect another source of run state, such as a later live connection, see [the state interface](specs/004-omniverse-run-replay/contracts/state-interface.md). See also [the application contract](specs/004-omniverse-run-replay/contracts/application.md) and [its changes](specs/005-omniverse-crane-load-models/contracts/application.md).

## Input files

- **Warehouse**: aisle count, racks, bays, levels, cell dimensions, crane parameters, transfer points at each aisle end, storage location rule, and initial stock.
- **Scenario**: seed, duration, warm-up, and either generation parameters or an explicit list of timed orders.

See [the input format](specs/001-headless-throughput-sim/contracts/input-format.md) for details.

## Output files

| File | Content |
|---|---|
| `report.md` | Run identification, all metrics with definitions and units, and modeling assumptions |
| `result.json` | The same results in a machine-readable form with stable metric names |
| `orders.csv` | One row per order, with its times, crane, cell, transfer point, and outcome |
| `replay.json` | Only with `--replay`: everything the viewer needs to replay the run |

Identical inputs, seed, and software version give byte-identical files. See [the output format](specs/001-headless-throughput-sim/contracts/results.md) for details.

## Comparing warehouse variants

Warehouse designs can be compared by changing data only:

1. Copy the warehouse file, and change one thing at a time: for example, `aisle_count`, `crane`, `cell`, `bays_per_rack`, `levels_per_rack`, `storage_rule`, or `transfer_points`. `samples/variants/` has examples.
2. Run each variant with the same scenario file. With the same seed, generated orders have the same times, types, and articles in every variant.
3. Compare these fields of each `result.json`:
   - `metrics.throughput_per_hour`
   - `metrics.order_cycle_time_s` and `metrics.order_waiting_time_s`
   - `metrics.crane_utilization`
   - `metrics.backlog_orders`
   - `metrics.order_outcomes`

Check `run.warehouse.sha256` and `run.scenario.sha256` to confirm which inputs produced a result.

Order timing can change which cells orders receive, so compare individual orders only in a scenario like `samples/variants/spaced-orders.yaml`, whose orders are far enough apart that cranes are always idle.

The storage location rules do not consider how busy each crane is. `nearest_free` in particular fills the nearest cells of the lowest-numbered aisles first and can overload those cranes, so a low throughput may reflect the rule rather than the warehouse design. Every report lists all modeling assumptions.

## Time-stepped runs

Add `--time-stepped` to run the warehouse in fixed cycles, the way a plant reacts to a PLC. In each cycle, a controller reads and writes [a list of signals](specs/003-time-stepped-plant-model/contracts/signal-list.md), using per-axis positioning, and the plant advances by one time step. The input files stay the same, and the results have the same form, with the mode, cycle time, controller, and any faults added.

```text
uv run highbay-sim run samples/small-warehouse.yaml samples/daily-scenario.yaml --output out/stepped --time-stepped
uv run highbay-sim run samples/small-warehouse.yaml samples/daily-scenario.yaml --output out/event
uv run highbay-sim compare out/event out/stepped
```

`compare` shows every metric of two runs of the same inputs and how far they deviate. The sources of deviation are listed in each time-stepped report. `--replay` works as for event-based runs.

| Option | Default | Meaning |
|---|---|---|
| `--cycle-ms N` | 50 | Cycle time, as a whole number of milliseconds from 1 to 1,000 |
| `--controller FILE.py:CLASS` | built-in | Controller to use. This runs that file as code, so use only files you trust. |
| `--record-signals` | off | Also write `signals.csv`, with every change of every signal. It can reach about 100 MB per simulated hour in a large warehouse, so use it for short runs. |

A controller is a class that needs no arguments to create, and has a method `scan(self, signals)`, which is called once per cycle with a mapping from aisle number to that crane's signals. `tests/data/scripted_controller.py` is an example. Order handling stays in the simulation, and gives the controller transport jobs through the signals. A command that the plant cannot carry out does not stop the run: the plant reports a fault on that crane, and the fault is listed in the results.

No PLC can be connected yet: this feature prepares that connection. The plant model is ideal: drives have no position error, and safety functions are not modeled.

## Development

Viewer tests run in a headless browser, which needs to be downloaded once:

```text
uv run playwright install chromium
```

```text
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
```

Tests that need Omniverse Kit run only on request, as they take minutes and occupy the graphics card. They are skipped if Kit is not installed, and `HIGHBAY_KIT_DIR` can name its folder if it is not in the default place:

```text
uv run pytest -m omniverse
```

A `-m` on the command line replaces the default that leaves these tests out, so any other choice should add `and not omniverse`, for example `-m "not performance and not omniverse"`.

The logic in `omniverse/exts/highbay.replay/highbay/replay/core` also has to run in Kit's Python 3.12:

```text
uv run --isolated --python 3.12 pytest tests/omniverse
```

To measure the viewer's frame rate on your graphics hardware, write the planning-target replay and open the printed address with `?benchmark=1`:

```text
uv run python tests/performance/write_planning_target.py out/target
uv run highbay-sim view out/target --no-browser
```

The project was built with [Spec Kit](https://github.com/github/spec-kit). Each feature's specification, plan, and tasks are in `specs/`, and the project principles are in `.specify/memory/constitution.md`.
