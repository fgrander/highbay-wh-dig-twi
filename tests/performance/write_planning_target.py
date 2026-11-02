"""Writes results and replay data for the planning-target run to a directory.

Usage: uv run python tests/performance/write_planning_target.py OUTPUT_DIRECTORY
"""

import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from highbay_sim import __version__
from highbay_sim.config import WarehouseDefinition, content_hash
from highbay_sim.engine import simulate
from highbay_sim.metrics import calculate_metrics
from highbay_sim.orders import GeneratedOrders
from highbay_sim.outputs import REPLAY_FILE, RunInfo, write_outputs
from highbay_sim.replay import build_replay, write_replay

SECONDS_PER_DAY = 86400.0
WARM_UP_S = 3600.0
SEED = 1
ORDERS_PER_HOUR = 1000.0


def planning_target_document(storage_rule: str = "nearest_free") -> dict[str, Any]:
    """20 aisles, 2 racks each, 50 bays, and 50 levels: 100,000 cells, with some initial stock."""
    return {
        "schema_version": 1,
        "name": "planning-target",
        "layout": {
            "aisle_count": 20,
            "racks_per_aisle": 2,
            "bays_per_rack": 50,
            "levels_per_rack": 50,
            "cell": {"height_m": 1.5, "length_m": 3.2, "width_m": 1.5},
        },
        "crane": {
            "horizontal": {"speed_m_s": 3.0, "acceleration_m_s2": 0.5},
            "vertical": {"speed_m_s": 1.0, "acceleration_m_s2": 0.5},
            "pick_time_s": 12.0,
            "set_time_s": 12.0,
        },
        "transfer_points": {"default": {"left": ["inbound"], "right": ["outbound"]}},
        "storage_rule": storage_rule,
        "initial_stock": [
            {
                "location": {"aisle": aisle, "rack": rack, "bay": bay, "level": 1},
                "article": "A" if bay % 2 else "B",
            }
            for aisle in range(1, 21)
            for rack in (1, 2)
            for bay in range(1, 51)
        ],
    }


@dataclass(frozen=True)
class WriteTimes:
    results_s: float
    replay_s: float


def write_planning_target(directory: Path) -> WriteTimes:
    """Write the run's files, returning the time spent building and writing each."""
    document = planning_target_document()
    warehouse = WarehouseDefinition.model_validate(document)
    source = GeneratedOrders(SEED, ORDERS_PER_HOUR, 0.5, {"A": 1.0, "B": 1.0})
    record = simulate(warehouse, source, SEED, SECONDS_PER_DAY)
    metrics = calculate_metrics(record, WARM_UP_S)
    scenario_identity = {"seed": SEED, "orders_per_hour": ORDERS_PER_HOUR}
    info = RunInfo(
        software_version=__version__,
        seed=SEED,
        warehouse_name=warehouse.name,
        warehouse_sha256=content_hash(document),
        scenario_name="planning-target",
        scenario_sha256=content_hash(scenario_identity),
        duration_s=SECONDS_PER_DAY,
    )

    start = time.perf_counter()
    write_outputs(directory, info, metrics, record.orders)
    results_s = time.perf_counter() - start

    start = time.perf_counter()
    write_replay(directory / REPLAY_FILE, build_replay(record, warehouse, info, metrics))
    replay_s = time.perf_counter() - start
    return WriteTimes(results_s, replay_s)


if __name__ == "__main__":
    target = Path(sys.argv[1])
    times = write_planning_target(target)
    size_mb = (target / REPLAY_FILE).stat().st_size / 1_000_000
    print(f"Replay file: {size_mb:.1f} MB, written in {times.replay_s:.2f} s, in {target}")
