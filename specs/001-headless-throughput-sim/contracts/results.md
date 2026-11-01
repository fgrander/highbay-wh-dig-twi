# Contract: Output Files

A run writes three files to the output directory. They contain no timestamps or machine details, so identical inputs and software versions produce byte-identical files. Times are in seconds with 3 decimal places. Shares, occupancy, and throughput have 6 decimal places.

## `result.json`

```json
{
  "schema_version": 1,
  "run": {
    "software_version": "0.1.0",
    "seed": 42,
    "warehouse": { "name": "small-warehouse", "sha256": "..." },
    "scenario": { "name": "daily-scenario", "sha256": "..." },
    "duration_s": 86400.0,
    "window": { "start_s": 3600.0, "end_s": 86400.0 }
  },
  "metrics": {
    "throughput_per_hour": { "total": 0.0, "storage": 0.0, "retrieval": 0.0 },
    "order_cycle_time_s": { "mean": 0.0, "median": 0.0, "p95": 0.0, "max": 0.0 },
    "order_waiting_time_s": { "mean": 0.0, "median": 0.0, "p95": 0.0, "max": 0.0 },
    "crane_utilization": {
      "1": { "moving_loaded": 0.0, "moving_empty": 0.0, "handling": 0.0, "idle": 1.0 }
    },
    "backlog_orders": { "at_window_end": 0, "max_in_window": 0 },
    "storage_occupancy": { "at_window_start": 0.0, "at_window_end": 0.0 },
    "order_outcomes": { "generated": 0, "completed": 0, "unfinished": 0, "unfulfillable": 0 }
  },
  "definitions": { "throughput_per_hour": { "unit": "orders/hour", "definition": "..." } },
  "assumptions": ["..."]
}
```

- Metric names and units are stable within a `schema_version`.
- A statistic with no data is `null`, and appears as "not available" in the report.
- Utilization shares are between 0 and 1.

## Metric definitions

These definitions appear in `result.json` and `report.md`. The window is `warmup_s` to `duration_s`.

| Metric | Definition |
|---|---|
| Throughput | Orders with a completion time in the window, divided by the window length in hours |
| Order cycle time | Completion time minus arrival time, for orders completed in the window |
| Order waiting time | Start time minus arrival time, for orders started in the window |
| Crane utilization | Time in each activity within the window, divided by the window length; activities crossing a window boundary count only their share inside it |
| Backlog | Orders that have arrived but have not started and are not unfulfillable |
| Storage occupancy | Cells physically holding a load unit, divided by all cells |
| Order outcomes | Counts over the whole run, including warm-up |

Statistics: the mean is arithmetic, the median is the middle value or the average of the two middle values, and the 95th percentile uses the nearest-rank method. An order completed or started exactly at the window start counts as inside the window, as does one at the window end.

## `orders.csv`

One row per order, in order ID order, with this header:

```text
order_id,type,article,arrival_s,start_s,completion_s,crane,location,transfer_point,outcome,reason
```

- `location` is written as `aisle-rack-bay-level`, and `transfer_point` as `left` or `right`.
- `outcome` is `completed`, `unfinished`, or `unfulfillable`. `reason` is empty for completed orders. Otherwise it is `no_stock` for unfulfillable orders, `no_free_cell` for unfinished storage orders still waiting for a cell, or `run_ended` for other unfinished orders.
- Fields with no value are empty.

## `report.md`

A human-readable report with these sections, in this order:

1. Run identification: the same content as `run`
2. Throughput summary
3. Cycle and waiting times
4. Crane utilization by crane
5. Backlog, occupancy, and order outcomes
6. Metric definitions and units
7. Modeling assumptions and simplifications (FR-016)
