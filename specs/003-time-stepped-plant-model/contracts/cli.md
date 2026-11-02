# Contract: Command-Line Interface Changes

These changes extend the contracts of features 001 and 002. All existing behavior stays the same.

## `highbay-sim run WAREHOUSE SCENARIO --output DIRECTORY --time-stepped [options]`

Runs the warehouse in fixed cycles. The existing `--overwrite` and `--replay` options work as before.

| Option | Default | Meaning |
|---|---|---|
| `--time-stepped` | off | Use the plant model, rather than the event-based simulation |
| `--cycle-ms N` | 50 | Cycle time as a whole number of milliseconds from 1 to 1,000 |
| `--controller FILE.py:CLASS` | built-in | Controller class to load from a local Python file, which this runs as code |
| `--record-signals` | off | Also write `signals.csv` |

| Situation | Result |
|---|---|
| `--cycle-ms`, `--controller`, or `--record-signals` without `--time-stepped` | Message on standard error, exit code 2, before any simulation |
| A cycle time that is not a whole number from 1 to 1,000 | Message naming the value and the allowed range, exit code 2 |
| A controller file or class that cannot be loaded, or has no `scan` method | Message naming the problem, exit code 2 |
| A controller that raises an error during a run | Message with the cycle and the error, exit code 1, no result files |
| A fault during a run | Not an error: the run continues, and the fault is listed in the results, exit code 0 |

`signals.csv` counts as an output file, in the same way as `replay.json`: it needs `--overwrite` to be replaced, and it is deleted by an overwriting run that does not record signals.

## `highbay-sim compare RESULT_A RESULT_B`

Compares two runs and prints each metric of both, with the absolute and relative deviation of B from A. Each argument is a `result.json` file, or a directory containing one. It writes no files.

| Situation | Result |
|---|---|
| Both runs used the same warehouse and scenario hashes | Table on standard output, exit code 0 |
| Different warehouse or scenario hashes | Message naming the difference, exit code 2 |
| A file that is missing or cannot be read as a result | Message on standard error, exit code 2 |

The output also shows each run's mode and cycle time. A metric whose value in A is 0 shows only the absolute deviation.

## Exit codes

The meanings in the existing contract are unchanged: 0 for success, 1 for a failure, and 2 for invalid input or incorrect command usage.
