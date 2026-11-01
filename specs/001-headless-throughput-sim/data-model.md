# Data Model: Headless Throughput Simulation

Units are metres, seconds, and metres per second (squared). File formats are in [contracts/input-format.md](contracts/input-format.md).

## Configuration entities

### Warehouse Definition

| Field | Description | Validation |
|---|---|---|
| `name` | Variant name | Not empty |
| `aisle_count` | Number of aisles, numbered from 1 | Integer ≥ 1 |
| `racks_per_aisle` | Rack sides served per aisle, default 2 | 1 or 2 |
| `bays_per_rack`, `levels_per_rack` | Number of cells along and up each rack | Integers ≥ 1 |
| `cell` | Height, length, and width, the same for all cells | Each > 0 |
| `crane` | Crane parameters applied to every aisle | See Crane |
| `transfer_points` | Default per-end configuration and per-aisle overrides | See Transfer Point |
| `storage_rule` | `nearest_free` or `random_free` | One of these values |
| `initial_stock` | List of stock entries | See Stock Entry |

The cell count is `aisle_count × racks_per_aisle × bays_per_rack × levels_per_rack`.

### Storage Location

Identified by `aisle`, `rack`, `bay`, and `level`, all numbered from 1.

- Horizontal position: `(bay - 0.5) × cell length`
- Vertical position: `(level - 1) × cell height`

### Crane

| Field | Description | Validation |
|---|---|---|
| `horizontal`, `vertical` | Speed and acceleration for each axis | Each > 0 |
| `pick_time_s` | Time to pick up a load unit | ≥ 0 |
| `set_time_s` | Time to set down a load unit | ≥ 0 |

### Transfer Point

A role (`inbound` or `outbound`) at an end (`left` or `right`) of an aisle. Left is at horizontal position 0, right is at `bays_per_rack × cell length`, and both are at height 0.

Validation: after overrides, each aisle has at least one inbound and one outbound point. An end lists each role at most once. Overrides refer only to aisles that exist.

### Stock Entry

An `article` and a `location`. Validation: the location exists and appears only once.

### Scenario

| Field | Description | Validation |
|---|---|---|
| `name` | Scenario name | Not empty |
| `seed` | Seed for all randomness | Integer ≥ 0 |
| `duration_s` | Simulated period | > 0 |
| `warmup_s` | Time before the measurement window | ≥ 0 and < `duration_s` |
| `generated` or `orders` | Exactly one order definition | See below |

`generated` contains `orders_per_hour` (≥ 0), `storage_share` (0 to 1), and `article_weights` (non-negative, with a positive total).

`orders` is a list of `time_s` (≥ 0 and < `duration_s`), `type` (`storage` or `retrieval`), and `article`. An empty list is valid.

## Runtime entities

### Article

A stored goods type, identified by a text ID. Articles need no separate definition, and an article that has no stock simply makes its retrieval orders unfulfillable.

### Load Unit

A package of wood panels or a stack of paper on a pallet. It has an article and the time it was stored; initial stock has stored time 0, with ties resolved by location order. Its physical size is not modeled.

### Order

`order_id` (`O000001` onwards, by arrival order), `type`, `article`, `arrival_s`, and, once known, `location`, `crane` (equal to the aisle number), `transfer_point`, `start_s`, `completion_s`, and `outcome`.

```text
                    no free cell             cell released
arrived (storage) ---------------> waiting_for_cell ------+
      |                                                   v
      +-------------- cell reserved ---------------->  queued --> in_progress --> completed
                                                          ^
arrived (retrieval) ---- stock reserved ------------------+
      |
      +---- no available stock ----> unfulfillable

Any order not completed or unfulfillable when the run ends has the outcome unfinished.
```

An order counts as backlog from arrival until a crane starts it, or until it becomes unfulfillable.

### Cell states

```text
free --> reserved_for_storage --> occupied --> reserved_for_retrieval --> free
```

- Occupancy counts `occupied` and `reserved_for_retrieval` cells, because a load unit is physically there.
- A cell becomes `occupied` when the load unit is set down, and `free` when it is picked up.
- A cell in `reserved_for_storage` is not available to any other order.

### Crane Cycle

A cycle is one order's steps, each of which records a time span and activity:

| Order type | Steps |
|---|---|
| Storage | Move empty to inbound point → pick → move loaded to cell → set |
| Retrieval | Move empty to cell → pick → move loaded to outbound point → set |

The activities are `moving_empty`, `moving_loaded`, and `handling`; all other time is `idle`. Between orders, a crane stays at its last position.

When an aisle offers two points of the required type (FR-001b), the point with the shortest total travel time for the order is used, and the left end wins a tie:

- Storage: empty travel from the crane's position to the point, plus loaded travel from the point to the cell. The crane's position is taken when the cycle starts.
- Retrieval: loaded travel from the cell to the point.

### Simulation Event

A record with `time_s`, `sequence`, `kind`, and related IDs. Kinds: `order_arrived`, `order_waiting_for_cell`, `order_queued`, `order_unfulfillable`, `order_started`, `activity_started`, `load_picked`, `load_set`, `order_completed`. Metrics are calculated only from these events and the initial state, using the same stream that later consumers will receive.

### Run Result

The input identification, metrics, per-order records, metric definitions, and modeling assumptions. See [contracts/results.md](contracts/results.md).
