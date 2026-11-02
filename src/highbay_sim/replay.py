"""Builds and writes replay data, as in contracts/replay-format.md.

Replay data is built from a finished run, so writing it cannot affect the run's results. Times are
not rounded: rounding would merge closely spaced events, and the viewer could then show a state
that never occurred.
"""

import json
from pathlib import Path
from typing import Any

from highbay_sim.allocation import end_position
from highbay_sim.config import WarehouseDefinition
from highbay_sim.engine import OrderRecord, RunRecord
from highbay_sim.events import Location, SimulationEvent
from highbay_sim.metrics import Metrics, backlog_over_time
from highbay_sim.outputs import RunInfo, result_document

FORMAT_VERSION = 1
ORDER_COLUMNS = (
    "order_id",
    "type",
    "article",
    "arrival_s",
    "start_s",
    "completion_s",
    "crane",
    "location",
    "transfer_point",
    "outcome",
    "reason",
)
EVENT_COLUMNS = (
    "time_s",
    "kind",
    "order",
    "crane",
    "location",
    "activity",
    "end_s",
    "start_position",
    "target_position",
)


def first_backlog_peak_s(record: RunRecord, start_s: float, maximum: int) -> float:
    """Return the earliest time in the window at which the backlog equals its maximum."""
    backlog_at_start = 0
    for time_s, backlog in backlog_over_time(record.events):
        if time_s <= start_s:
            backlog_at_start = backlog
        elif backlog_at_start == maximum:
            return start_s
        elif backlog == maximum:
            return time_s
    return start_s


def build_replay(
    record: RunRecord, warehouse: WarehouseDefinition, info: RunInfo, metrics: Metrics
) -> dict[str, Any]:
    result = result_document(info, metrics)
    stock = sorted(
        (
            (
                entry.location.aisle,
                entry.location.rack,
                entry.location.bay,
                entry.location.level,
                entry.article,
            )
            for entry in warehouse.initial_stock
        ),
    )
    articles = sorted({row[4] for row in stock} | {order.article for order in record.orders})
    article_index = {article: index for index, article in enumerate(articles)}
    order_index = {order.order_id: index for index, order in enumerate(record.orders)}
    reported = result["metrics"]
    return {
        "format_version": FORMAT_VERSION,
        "run": result["run"],
        "warehouse": _warehouse_part(warehouse),
        "articles": articles,
        "initial_stock": [[*row[:4], article_index[row[4]]] for row in stock],
        "order_columns": list(ORDER_COLUMNS),
        "orders": [_order_row(order, article_index) for order in record.orders],
        "event_columns": list(EVENT_COLUMNS),
        "events": [_event_row(event, order_index) for event in record.events],
        "reported": {
            "backlog_orders": reported["backlog_orders"],
            "first_backlog_peak_s": first_backlog_peak_s(
                record, metrics.window_start_s, metrics.backlog_max_in_window
            ),
            "storage_occupancy": reported["storage_occupancy"],
            "order_outcomes": reported["order_outcomes"],
        },
    }


def replay_text(replay: dict[str, Any]) -> str:
    return json.dumps(replay, separators=(",", ":")) + "\n"


def write_replay(path: Path, replay: dict[str, Any]) -> None:
    path.write_text(replay_text(replay), encoding="utf-8", newline="\n")


def _warehouse_part(warehouse: WarehouseDefinition) -> dict[str, Any]:
    aisles = range(1, warehouse.layout.aisle_count + 1)
    points = warehouse.transfer_points
    return {
        "layout": warehouse.layout.model_dump(),
        "crane": warehouse.crane.model_dump(),
        "transfer_points": {
            str(aisle): points.aisles.get(aisle, points.default).model_dump() for aisle in aisles
        },
        "crane_start_positions": {
            str(aisle): list(
                end_position(warehouse.layout, warehouse.ends_with_role(aisle, "inbound")[0])
            )
            for aisle in aisles
        },
    }


def _order_row(order: OrderRecord, article_index: dict[str, int]) -> list[Any]:
    return [
        order.order_id,
        order.order_type,
        article_index[order.article],
        order.arrival_s,
        order.start_s,
        order.completion_s,
        order.crane,
        _location(order.location),
        order.transfer_point,
        order.outcome,
        order.reason,
    ]


def _event_row(event: SimulationEvent, order_index: dict[str, int]) -> list[Any]:
    return [
        event.time_s,
        event.kind,
        order_index[event.order_id],
        event.crane,
        _location(event.location),
        event.activity,
        event.end_s,
        None if event.start_position is None else list(event.start_position),
        None if event.target_position is None else list(event.target_position),
    ]


def _location(location: Location | None) -> list[int] | None:
    return None if location is None else list(location)
