# Contract: Input Files

Both files are YAML with `schema_version: 1`. Unknown fields are rejected, so typing errors are not silently ignored. Field meanings and validation rules are in [data-model.md](../data-model.md).

## Warehouse file

```yaml
schema_version: 1
name: small-warehouse
layout:
  aisle_count: 4
  racks_per_aisle: 2        # optional, default 2
  bays_per_rack: 40
  levels_per_rack: 10
  cell:
    height_m: 1.5
    length_m: 3.2
    width_m: 1.5
crane:
  horizontal: { speed_m_s: 3.0, acceleration_m_s2: 0.5 }
  vertical: { speed_m_s: 1.0, acceleration_m_s2: 0.5 }
  pick_time_s: 12.0
  set_time_s: 12.0
transfer_points:
  default:
    left: [inbound]
    right: [outbound]
  aisles:                   # optional overrides, by aisle number
    3:
      left: [inbound, outbound]
      right: [inbound, outbound]
storage_rule: nearest_free  # or random_free
initial_stock:              # optional
  - { location: { aisle: 1, rack: 1, bay: 1, level: 1 }, article: oak-panel-18mm }
  - { location: { aisle: 1, rack: 2, bay: 1, level: 1 }, article: paper-a4-80g }
```

The values above are illustrative and are not real equipment data.

## Scenario file

A scenario has exactly one of `generated` or `orders`.

```yaml
schema_version: 1
name: daily-scenario
seed: 42
duration_s: 86400
warmup_s: 3600
generated:
  orders_per_hour: 60
  storage_share: 0.5
  article_weights:
    oak-panel-18mm: 3
    paper-a4-80g: 1
```

```yaml
schema_version: 1
name: verification-v1
seed: 1
duration_s: 3600
warmup_s: 0
orders:
  - { time_s: 0, type: storage, article: A }
  - { time_s: 30, type: retrieval, article: A }
```

Explicit orders with the same time keep their file order. The seed is still required, because the `random_free` storage rule uses it.
