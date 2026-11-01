# Highbay Warehouse Digital Twin

A command-line throughput simulation of one high-bay warehouse, written in Python. It runs with no graphical interface. A warehouse and an order scenario are defined in YAML files, and each run writes a report of throughput metrics.

The 3D view and live data connections are planned as later features.

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

## Development

```text
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src
```

The project was built with [Spec Kit](https://github.com/github/spec-kit). Its specification, plan, and tasks are in `specs/001-headless-throughput-sim/`, and the project principles are in `.specify/memory/constitution.md`.
