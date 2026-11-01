# Research: Headless Throughput Simulation

The project owner requires the simulation to run entirely in Python. The other decisions are proposals made during planning.

## Language and runtime

- **Decision**: Python 3.12 or newer, managed with uv.
- **Rationale**: Python is the project owner's requirement for the simulation. The SC-004 target needs about 24,000 orders, a modest event count that Python handles well within 60 seconds. Results are easy to analyze in common data tools, and uv is already installed on the development machine.
- **Alternatives considered**: TypeScript would share one language with a browser-based 3D view, but Node.js is not installed and analysis tooling is weaker. C#/.NET 8 is installed and faster, and suits a Unity 3D view, but it ties the later visualization choice to that ecosystem earlier than needed. Rust is the fastest option, but the speed is not needed and iteration on the model would be slower.

## Simulation engine

- **Decision**: A small custom discrete-event loop using a priority queue ordered by simulated time and then a sequence number.
- **Rationale**: Only order arrivals and crane step completions are needed. Direct control over tie-breaking supports exact reproducibility (Principle II).
- **Alternatives considered**: SimPy is mature, but its process and resource features are not needed here and it would make event ordering less explicit.

## Reproducibility

- **Decision**: Use separate `random.Random` instances for order generation and for storage location choice, each seeded from a SHA-256 hash of the run seed and the stream name. Iterate only over ordered collections. Write no timestamps or machine details to outputs. Format numbers in outputs with a fixed precision.
- **Rationale**: Separate streams keep the generated order sequence identical across warehouse variants (User Story 3, scenario 2).
- **Alternatives considered**: One shared random stream would make the order sequence depend on the warehouse's storage decisions.

## Input format and content identification

- **Decision**: Hand-editable YAML files, validated by pydantic models plus cross-field checks, with every problem reported by field path. Identify inputs with a SHA-256 hash of their parsed content in canonical JSON.
- **Rationale**: YAML is readable and works well in version control. Hashing parsed content rather than file bytes keeps the hash stable across line-ending conversion, which is active in this repository's Git configuration (`core.autocrlf=true`).
- **Alternatives considered**: JSON does not allow comments and is harder to edit by hand. TOML handles long nested lists poorly.

## Crane motion model

- **Decision**: A symmetric trapezoidal velocity profile for each axis, starting and ending at rest. For distance `d`, speed `v`, and acceleration `a`, the time is `d/v + v/a` when `d >= v²/a`, and otherwise `2·sqrt(d/a)`. A movement takes the longer of its horizontal and vertical times.
- **Rationale**: This is the standard calculation for stacker crane cycle times, it satisfies FR-010, and results can be checked by hand.
- **Alternatives considered**: Modeling jerk limits adds accuracy but requires data not yet available and makes hand verification harder.

## Geometry

- **Decision**: Horizontal position is the center of the cell's bay, `(bay - 0.5) × cell length`. Vertical position is the floor of the cell's level, `(level - 1) × cell height`. Aisle ends are at `0` (left) and `bays × cell length` (right), at height `0`.
- **Consequence**: Cell width does not affect travel, because cranes do not change aisles and fork movement is part of the handling time. It is validated and recorded for later use, such as the 3D view. This narrows the wording of FR-001, which says that cell dimensions determine travel distances.
- **Alternatives considered**: Adding beam thickness and clearances needs data that is not yet available.

## Order handling

- **Decision**: Assign a cell when an order arrives and put the order in the queue of that aisle's crane, served first-come, first-served.
  - A storage order reserves a free cell under the chosen rule. If none is free, it waits in a warehouse-wide queue and receives a cell as soon as one is released.
  - A retrieval order reserves the oldest stored, unreserved load unit of its article across all aisles. If none exists at arrival, it is immediately unfulfillable.
  - A cell is released when a crane picks up its load unit, and its load unit becomes available when the crane sets it down.
- **Rationale**: This is deterministic, simple, and consistent with the spec's assumptions. The per-order assignment is visible in the per-order record.
- **Alternatives considered**: Choosing cells only when a crane becomes free would better reflect some warehouse control systems, but it complicates aisle assignment and hand verification.

## Crane start position

- **Decision**: Each crane starts at rest at its aisle's first inbound transfer point, with the left end before the right.
- **Rationale**: The spec gives no start position, and any fixed rule keeps runs reproducible. The warm-up period reduces its effect on results.

## Order generation

- **Decision**: Generated orders arrive as a Poisson process, meaning exponentially distributed gaps at the configured rate. The type and the article are drawn independently using the configured share and weights.
- **Rationale**: This is the usual default for independent arrivals and needs only the parameters listed in FR-005.
- **Alternatives considered**: Time-of-day profiles are useful later, when real order data is available.

## Percentiles

- **Decision**: The 95th percentile and median use a stated definition: nearest-rank for the percentile, and the middle value or average of the two middle values for the median.
- **Rationale**: A written definition is required by Principle III, and nearest-rank always returns a value that actually occurred.

## Performance approach

- **Decision**: Keep free cells for the nearest rule in a priority queue using precomputed travel times, keep free cells for the random rule in an indexable list with swap-removal, and keep stock per article in arrival order.
- **Rationale**: Each lookup stays far below a scan of all 100,000 cells. A performance test measures SC-004 directly.
