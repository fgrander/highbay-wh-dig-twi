# Contract: Replay File

`replay.json` is compact UTF-8 JSON with Unix line endings. It contains no timestamps of when it was written and no machine details, so identical inputs and software versions give byte-identical files. Times are in seconds and are not rounded: each is the shortest decimal that reads back as the same value, so the order of closely spaced events is never lost. Positions are `[horizontal_m, vertical_m]`.

```json
{
  "format_version": 1,
  "run": {
    "software_version": "0.2.0",
    "seed": 42,
    "warehouse": { "name": "small-warehouse", "sha256": "..." },
    "scenario": { "name": "daily-scenario", "sha256": "..." },
    "duration_s": 86400.0,
    "window": { "start_s": 3600.0, "end_s": 86400.0 }
  },
  "warehouse": {
    "layout": {
      "aisle_count": 4,
      "racks_per_aisle": 2,
      "bays_per_rack": 40,
      "levels_per_rack": 10,
      "cell": { "height_m": 1.5, "length_m": 3.2, "width_m": 1.5 }
    },
    "crane": {
      "horizontal": { "speed_m_s": 3.0, "acceleration_m_s2": 0.5 },
      "vertical": { "speed_m_s": 1.0, "acceleration_m_s2": 0.5 },
      "pick_time_s": 12.0,
      "set_time_s": 12.0
    },
    "transfer_points": { "1": { "left": ["inbound"], "right": ["outbound"] } },
    "crane_start_positions": { "1": [0.0, 0.0] }
  },
  "articles": ["oak-panel-18mm", "paper-a4-80g"],
  "initial_stock": [[1, 1, 1, 1, 0]],
  "order_columns": ["order_id", "type", "article", "arrival_s", "start_s", "completion_s", "crane", "location", "transfer_point", "outcome", "reason"],
  "orders": [["O000001", "storage", 0, 13.142, 13.142, 40.72, 1, [1, 1, 1, 2], "left", "completed", ""]],
  "event_columns": ["time_s", "kind", "order", "crane", "location", "activity", "end_s", "start_position", "target_position"],
  "events": [[13.142, "order_arrived", 0, null, null, null, null, null, null]],
  "reported": {
    "backlog_orders": { "at_window_end": 0, "max_in_window": 0 },
    "first_backlog_peak_s": 3600.0,
    "storage_occupancy": { "at_window_start": 0.0, "at_window_end": 0.0 },
    "order_outcomes": { "generated": 0, "completed": 0, "unfinished": 0, "unfulfillable": 0 }
  }
}
```

## Fields

- `transfer_points` and `crane_start_positions` have one entry for each aisle.
- `initial_stock` rows are `[aisle, rack, bay, level, article_index]`, sorted by location.
- `orders` rows follow `order_columns`. `article` is an index into `articles`. A value that is empty in `orders.csv` is `null` here, except `reason`, which is `""`.
- `events` rows follow `event_columns`, in event order. `order` is an index into `orders`. `kind` and `activity` use the names from the simulation's events.
- `start_position` and `target_position` are set only on `activity_started` rows whose activity is `moving_empty` or `moving_loaded`.
- `reported` uses the same names and values as `result.json`, except `first_backlog_peak_s`.

## `first_backlog_peak_s`

The earliest simulated time in the measurement window at which, after all events at that time are applied, the backlog equals `backlog_orders.max_in_window`. If the maximum is carried over from before the window, this is the start of the window.

## Versions

`format_version` changes when a change to this format would prevent an existing viewer from reading a file correctly. A viewer refuses a version it does not support, with a message naming both versions.
