"""SC-004: the planning-target warehouse must simulate one day in under 60 seconds.

The time limit was set for a typical desktop computer, so a pass applies to the machine running
this test. At this load the cranes run out of capacity and a backlog builds up, which the timing
check allows and which makes the run harder, as queues are at their longest.
"""

import time

import pytest

from conftest import minimal_warehouse_dict
from highbay_sim.config import WarehouseDefinition
from highbay_sim.engine import simulate
from highbay_sim.metrics import calculate_metrics
from highbay_sim.orders import GeneratedOrders

TIME_LIMIT_S = 60.0
SECONDS_PER_DAY = 86400.0


def planning_target_warehouse(storage_rule: str) -> WarehouseDefinition:
    content = minimal_warehouse_dict()
    content["layout"].update(
        aisle_count=20,
        racks_per_aisle=2,
        bays_per_rack=50,
        levels_per_rack=50,
    )
    content["storage_rule"] = storage_rule
    content["initial_stock"] = [
        {"location": {"aisle": aisle, "rack": 1, "bay": bay, "level": 1}, "article": "A"}
        for aisle in range(1, 21)
        for bay in range(1, 51)
    ]
    return WarehouseDefinition.model_validate(content)


@pytest.mark.performance
@pytest.mark.parametrize("storage_rule", ["nearest_free", "random_free"])
def test_planning_target_runs_within_the_time_limit(storage_rule: str) -> None:
    warehouse = planning_target_warehouse(storage_rule)
    source = GeneratedOrders(1, 1000.0, 0.5, {"A": 1.0})

    start = time.perf_counter()
    record = simulate(warehouse, source, 1, SECONDS_PER_DAY)
    metrics = calculate_metrics(record, 3600.0)
    elapsed = time.perf_counter() - start

    assert record.cell_count == 100_000
    assert record.crane_count == 20
    assert metrics.orders_generated > 23_000
    assert elapsed < TIME_LIMIT_S
