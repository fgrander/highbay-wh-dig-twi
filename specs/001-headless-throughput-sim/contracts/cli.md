# Contract: Command-Line Interface

The program is `highbay-sim`. It needs no display and no network access.

## `highbay-sim validate WAREHOUSE SCENARIO`

Checks both files without simulating.

- On success, prints a one-line confirmation including the cell and aisle counts.
- On failure, prints every problem to standard error, one per line:

```text
<file>: <field path>: <problem>
```

Example:

```text
warehouse.yaml: transfer_points.aisles.3: aisle 3 has no outbound transfer point
```

## `highbay-sim run WAREHOUSE SCENARIO --output DIRECTORY [--overwrite]`

Validates the inputs, runs the simulation, and writes the files described in [results.md](results.md).

- Validation failures are reported as for `validate`, and no simulation starts.
- If an output file already exists, the command fails unless `--overwrite` is given.
- On success, prints the output directory and total throughput.

## `highbay-sim --version`

Prints the software version recorded in results.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Unexpected failure, or output could not be written |
| 2 | Invalid input or incorrect command usage |
