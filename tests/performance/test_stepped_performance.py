"""SC-005: the planning-target warehouse must simulate one hour in cycles in under 60 seconds.

The time limit was set for a typical desktop computer, so a pass applies to the machine running
this test. At this load the cranes run out of capacity, so they work for the whole hour.
"""

import time

import pytest
from test_benchmark import planning_target_warehouse

from highbay_sim.metrics import calculate_metrics
from highbay_sim.orders import GeneratedOrders
from highbay_sim.stepped import simulate_stepped

TIME_LIMIT_S = 60.0
SECONDS_PER_HOUR = 3600.0
ORDERS_PER_HOUR = 1000.0


@pytest.mark.performance
@pytest.mark.parametrize("storage_rule", ["nearest_free", "random_free"])
def test_one_hour_at_the_planning_target(storage_rule: str) -> None:
    warehouse = planning_target_warehouse(storage_rule)
    source = GeneratedOrders(1, ORDERS_PER_HOUR, 0.5, {"A": 1.0})
    start = time.perf_counter()
    run = simulate_stepped(warehouse, source, 1, SECONDS_PER_HOUR)
    metrics = calculate_metrics(run.record, 0.0)
    elapsed = time.perf_counter() - start
    print(f"{storage_rule}: {elapsed:.1f} s, {metrics.orders_completed} orders completed")
    assert elapsed < TIME_LIMIT_S
    assert metrics.orders_completed > 0
    assert run.faults == ()
