# Contract: Library Interfaces

These are the boundaries required by Constitution Principles I and IV. Signatures show intent; exact types are settled during implementation.

```python
class OrderSource(Protocol):
    def orders(self, duration_s: float) -> Iterable[OrderRequest]:
        """Yield requests in non-decreasing arrival time, each with arrival_s < duration_s."""

def simulate(
    warehouse: WarehouseDefinition,
    order_source: OrderSource,
    seed: int,
    duration_s: float,
    on_event: Callable[[SimulationEvent], None] | None = None,
) -> RunRecord:
    """Run one simulation. Same arguments and version give the same events and record."""

def calculate_metrics(record: RunRecord, warmup_s: float) -> Metrics:
    """Calculate all metrics from a run's events and initial state, without re-simulating."""
```

## Rules

- `simulate` performs no file, network, or display access, and does not read the system clock.
- `WarehouseDefinition`, including its initial stock, is the input boundary for all warehouse data, and `OrderSource` is the boundary for orders. File loading in `config.py` only builds these objects. A later live source can supply either one without changing the engine.
- `GeneratedOrders` and `ExplicitOrders` are the only `OrderSource` implementations in this feature. A live source can later implement the same interface.
- `on_event` is called in event order. It can only observe: events are immutable, and consumers cannot change simulation state. The later 3D view can use this stream, or a saved copy of it.
- Results do not depend on whether `on_event` is provided.
