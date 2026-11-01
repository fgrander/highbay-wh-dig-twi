"""Shared helpers that build valid inputs in the form of contracts/input-format.md."""

from pathlib import Path
from typing import Any

import yaml


def minimal_warehouse_dict() -> dict[str, Any]:
    """One aisle, one rack, 5 bays, 2 levels: the warehouse used for hand calculations."""
    return {
        "schema_version": 1,
        "name": "minimal",
        "layout": {
            "aisle_count": 1,
            "racks_per_aisle": 1,
            "bays_per_rack": 5,
            "levels_per_rack": 2,
            "cell": {"height_m": 3.0, "length_m": 4.0, "width_m": 1.5},
        },
        "crane": {
            "horizontal": {"speed_m_s": 2.0, "acceleration_m_s2": 1.0},
            "vertical": {"speed_m_s": 1.0, "acceleration_m_s2": 1.0},
            "pick_time_s": 10.0,
            "set_time_s": 10.0,
        },
        "transfer_points": {"default": {"left": ["inbound"], "right": ["outbound"]}},
        "storage_rule": "nearest_free",
        "initial_stock": [],
    }


def minimal_scenario_dict() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "name": "minimal-scenario",
        "seed": 1,
        "duration_s": 3600,
        "warmup_s": 0,
        "orders": [],
    }


def write_yaml(path: Path, content: dict[str, Any]) -> Path:
    path.write_text(yaml.safe_dump(content, sort_keys=False), encoding="utf-8", newline="\n")
    return path
