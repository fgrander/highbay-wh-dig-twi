# Contract: Result Changes

These changes extend `specs/001-headless-throughput-sim/contracts/results.md`. Event-based runs do not contain any of the additions, so their files stay byte-identical apart from the software version (SC-009). The schema version stays the same, as all additions are optional fields.

## `result.json`

A time-stepped run adds `run.execution` and a top-level `faults` list:

```json
{
  "run": {
    "execution": {
      "mode": "time_stepped",
      "cycle_ms": 50,
      "controller": { "name": "built-in", "sha256": null },
      "signal_list_version": 1
    }
  },
  "faults": [
    {
      "cycle": 1204,
      "time_s": 60.2,
      "crane": 1,
      "code": 6,
      "name": "place_occupied",
      "description": "The cell at aisle 1, rack 2, bay 4, level 3 already holds a load unit."
    }
  ]
}
```

- For a controller loaded from a file, `name` is `FILE.py:CLASS` using the file's name only, and `sha256` is the hash of the file.
- `faults` is empty if there were none.
- `assumptions` also lists the plant model's simplifications, and the sources of deviation in [research.md](../research.md).
- Metrics use the same names, definitions, units, and rounding as event-based runs.

## `report.md`

A time-stepped run adds two sections: "Execution", with the fields above, and "Faults", with a table of faults, or a sentence saying there were none.

## `orders.csv`

Unchanged, as the columns and their meaning are the same in both modes.

## `replay.json`

The format version stays 1, and the viewer ignores the added `run.execution` field. Events have the same form as those of an event-based run. See [the replay format](../../002-3d-run-replay/contracts/replay-format.md).

## `signals.csv`

Written only with `--record-signals`, with Unix line endings and no timestamps or machine details. Its first row lists the initial value of each signal at cycle 0, and later rows list changes only.

| Column | Content |
|---|---|
| `cycle` | Cycle number, starting at 0 |
| `time_s` | Simulated time of the cycle's start, in shortest exact decimal form |
| `crane` | Aisle number of the crane |
| `signal` | Signal name from the [signal list](signal-list.md) |
| `value` | New value: `true` or `false`, or a number in shortest exact decimal form |

Rows are in order of cycle, crane, and signal list. Identical inputs give byte-identical files, and recording does not change any other output (FR-019).
