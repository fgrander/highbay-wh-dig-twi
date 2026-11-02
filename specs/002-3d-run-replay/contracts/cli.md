# Contract: Command-Line Interface Changes

These changes extend `specs/001-headless-throughput-sim/contracts/cli.md`. All existing behavior stays the same.

## `highbay-sim run WAREHOUSE SCENARIO --output DIRECTORY [--overwrite] [--replay]`

With `--replay`, the run also writes `replay.json` to the output directory, as described in [replay-format.md](replay-format.md).

- Without `--replay`, no replay file is written.
- `report.md`, `result.json`, and `orders.csv` are byte-identical with and without `--replay`.
- An existing `replay.json` counts as an existing output file, so it needs `--overwrite` to be replaced when `--replay` is given.
- With `--overwrite` but without `--replay`, an existing `replay.json` is deleted, so that it can never be viewed as if it belonged to the new results.
- Without `--overwrite` and without `--replay`, an existing `replay.json` counts as an existing output file too, so the run fails as for other existing outputs.

## `highbay-sim view PATH [--port PORT] [--no-browser]`

Starts the local viewer for one replay. `PATH` is a `replay.json` file, or a directory containing one.

- Serves the viewer at `http://127.0.0.1:<port>/`, using a free port unless `--port` is given.
- Opens the default web browser, unless `--no-browser` is given.
- Prints the address, and how to stop the viewer. It runs until stopped with Ctrl+C.
- Needs no internet connection, and changes no files.
- Accepts only GET and HEAD requests. Other request methods are refused.
- Only the viewer's own files and the chosen replay file are served.

A file that cannot be read as a valid replay opens in the viewer with an error message. Checks done before starting:

| Situation | Result |
|---|---|
| `PATH` does not exist, or a directory has no `replay.json` | Message on standard error, exit code 2 |
| The requested port cannot be used | Message on standard error, exit code 1 |
| Stopped with Ctrl+C | Exit code 0 |

## Exit codes

The meanings in the existing contract are unchanged: 0 for success, 1 for a failure, and 2 for invalid input or incorrect command usage.
