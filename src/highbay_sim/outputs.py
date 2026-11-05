"""The output files of a run: report.md, result.json, and orders.csv.

Files contain no timestamps or machine details and always use Unix line endings, so identical
inputs and software versions give byte-identical files.
"""

import csv
import io
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from highbay_sim.engine import OrderRecord
from highbay_sim.metrics import DEFINITIONS, Metrics, TimeStatistics
from highbay_sim.signals import Fault

REPLAY_FILE = "replay.json"
SIGNAL_FILE = "signals.csv"
OUTPUT_FILES = ("report.md", "result.json", "orders.csv", REPLAY_FILE, SIGNAL_FILE)
RESULT_SCHEMA_VERSION = 1
TIME_DECIMALS = 3
SHARE_DECIMALS = 6
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
NOT_AVAILABLE = "not available"
ASSUMPTIONS = (
    "Each aisle has one crane, which handles one load unit at a time and completes one order per "
    "cycle. Dual-command cycles, multi-load handling, and cranes changing aisles are not modeled.",
    "A crane movement uses a symmetric trapezoidal velocity profile on each axis, starting and "
    "ending at rest, and takes as long as the slower axis. Jerk limits are not modeled.",
    "Crane speed and acceleration do not depend on the weight of the load unit.",
    "A cell's horizontal position is the center of its bay and its vertical position is the "
    "floor of its level. Beam thickness and clearances are not modeled.",
    "Cell width does not affect travel, because cranes do not change aisles and fork movement is "
    "part of the handling time.",
    "All cells have the same dimensions, every load unit fits every cell, and each cell holds one "
    "load unit. Load unit dimensions are not checked, and double-deep storage is not modeled.",
    "All transfer points are at ground level. Load units are always available at inbound points "
    "and removed immediately from outbound points, so transfer points never block a crane. An "
    "order is not tied to a specific transfer point, and conveyors are not modeled.",
    "A crane starts at the first inbound point of its aisle, left before right, and otherwise "
    "waits where it finished its last order.",
    "An order receives its cell when it arrives and is then served first-come, first-served by "
    "that aisle's crane. Storage location rules do not consider how busy each crane is, so "
    "individual aisles can be overloaded while others are free.",
    "Retrievals take the oldest stored load unit of the article. A retrieval with no stored, "
    "unreserved load unit at arrival is unfulfillable and does not wait for incoming stock.",
    "Generated orders arrive as a Poisson process at a constant rate, with no time-of-day profile.",
    "Metrics are calculated for the measurement window after the warm-up, except order outcomes, "
    "which cover the whole run.",
    "Equipment failures, maintenance, staffing, and energy use are not modeled.",
)
TIME_STEPPED_ASSUMPTIONS = (
    "The plant advances in fixed cycles. Each movement and handling step ends on the next cycle "
    "boundary, so it takes on average half a cycle longer than in an event-based run.",
    "The job handshake between order handling and the controller takes one cycle per order.",
    "An order's arrival takes effect at the next cycle boundary, while keeping its exact time.",
    "Because timing shifts slightly, an arrival and a released cell can swap order compared with "
    "an event-based run, which can change a chosen cell, especially with a random storage rule.",
    "Drives are ideal: they follow the speed and acceleration limits exactly, with no position "
    "error, sensor noise, or stopping distance. Safety functions are not modeled.",
    "Fork motion is not modeled: handling takes the pick and set times from the crane parameters.",
    "A movement of zero distance, or a movement outside a transport job, does not count as crane "
    "work. A movement can start only while both axes of the crane are at rest.",
)


@dataclass(frozen=True)
class Execution:
    """How a time-stepped run was carried out."""

    cycle_ms: int
    controller_name: str
    controller_sha256: str | None
    signal_list_version: int
    plc: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class RunInfo:
    software_version: str
    seed: int
    warehouse_name: str
    warehouse_sha256: str
    scenario_name: str
    scenario_sha256: str
    duration_s: float
    execution: Execution | None = None


def existing_outputs(directory: Path) -> list[Path]:
    return [directory / name for name in OUTPUT_FILES if (directory / name).exists()]


def write_outputs(
    directory: Path,
    info: RunInfo,
    metrics: Metrics,
    orders: tuple[OrderRecord, ...],
    faults: tuple[Fault, ...] = (),
) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    result = result_document(info, metrics, faults)
    _write(directory / "result.json", json.dumps(result, indent=2) + "\n")
    _write(directory / "report.md", report_text(info, result))
    _write(directory / "orders.csv", orders_csv(orders))


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def _time(value: float) -> float:
    return round(value, TIME_DECIMALS)


def _share(value: float) -> float:
    return round(value, SHARE_DECIMALS)


def _statistics(statistics: TimeStatistics) -> dict[str, float | None]:
    return {
        name: None if value is None else _time(value)
        for name, value in (
            ("mean", statistics.mean),
            ("median", statistics.median),
            ("p95", statistics.p95),
            ("max", statistics.max),
        )
    }


def result_document(
    info: RunInfo, metrics: Metrics, faults: tuple[Fault, ...] = ()
) -> dict[str, Any]:
    document = _base_document(info, metrics)
    if info.execution is not None:
        document["run"]["execution"] = {
            "mode": "time_stepped",
            "cycle_ms": info.execution.cycle_ms,
            "controller": {
                "name": info.execution.controller_name,
                "sha256": info.execution.controller_sha256,
            },
            "signal_list_version": info.execution.signal_list_version,
        }
        document["assumptions"] += TIME_STEPPED_ASSUMPTIONS
        document["faults"] = [
            {
                "cycle": fault.cycle,
                "time_s": fault.time_s,
                "crane": fault.crane,
                "code": int(fault.code),
                "name": fault.code.name.lower(),
                "description": fault.description,
            }
            for fault in faults
        ]
        if info.execution.plc is not None:
            document["plc"] = dict(info.execution.plc)
    return document


def _base_document(info: RunInfo, metrics: Metrics) -> dict[str, Any]:
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "run": {
            "software_version": info.software_version,
            "seed": info.seed,
            "warehouse": {"name": info.warehouse_name, "sha256": info.warehouse_sha256},
            "scenario": {"name": info.scenario_name, "sha256": info.scenario_sha256},
            "duration_s": _time(info.duration_s),
            "window": {
                "start_s": _time(metrics.window_start_s),
                "end_s": _time(metrics.window_end_s),
            },
        },
        "metrics": {
            "throughput_per_hour": {
                "total": _share(metrics.throughput_total),
                "storage": _share(metrics.throughput_storage),
                "retrieval": _share(metrics.throughput_retrieval),
            },
            "order_cycle_time_s": _statistics(metrics.order_cycle_time),
            "order_waiting_time_s": _statistics(metrics.order_waiting_time),
            "crane_utilization": {
                str(crane): {
                    "moving_loaded": _share(share.moving_loaded),
                    "moving_empty": _share(share.moving_empty),
                    "handling": _share(share.handling),
                    "idle": _share(share.idle),
                }
                for crane, share in metrics.crane_utilization.items()
            },
            "backlog_orders": {
                "at_window_end": metrics.backlog_at_window_end,
                "max_in_window": metrics.backlog_max_in_window,
            },
            "storage_occupancy": {
                "at_window_start": _share(metrics.occupancy_at_window_start),
                "at_window_end": _share(metrics.occupancy_at_window_end),
            },
            "order_outcomes": {
                "generated": metrics.orders_generated,
                "completed": metrics.orders_completed,
                "unfinished": metrics.orders_unfinished,
                "unfulfillable": metrics.orders_unfulfillable,
            },
        },
        "definitions": DEFINITIONS,
        "assumptions": list(ASSUMPTIONS),
    }


def _shown(value: float | None, decimals: int) -> str:
    return NOT_AVAILABLE if value is None else f"{value:.{decimals}f}"


def report_text(info: RunInfo, result: dict[str, Any]) -> str:
    metrics = result["metrics"]
    window = result["run"]["window"]
    throughput = metrics["throughput_per_hour"]
    cycle = metrics["order_cycle_time_s"]
    waiting = metrics["order_waiting_time_s"]
    backlog = metrics["backlog_orders"]
    occupancy = metrics["storage_occupancy"]
    outcomes = metrics["order_outcomes"]

    lines = [
        f"# Simulation report: {info.warehouse_name} / {info.scenario_name}",
        "",
        "## Run identification",
        "",
        f"- Software version: {info.software_version}",
        f"- Seed: {info.seed}",
        f"- Warehouse: {info.warehouse_name} (SHA-256 `{info.warehouse_sha256}`)",
        f"- Scenario: {info.scenario_name} (SHA-256 `{info.scenario_sha256}`)",
        f"- Simulated duration: {_shown(info.duration_s, TIME_DECIMALS)} s",
        (
            f"- Measurement window: {_shown(window['start_s'], TIME_DECIMALS)} s to "
            f"{_shown(window['end_s'], TIME_DECIMALS)} s"
        ),
        "",
        "## Throughput",
        "",
        "| | Orders/hour |",
        "|---|---|",
        f"| Total | {_shown(throughput['total'], SHARE_DECIMALS)} |",
        f"| Storage | {_shown(throughput['storage'], SHARE_DECIMALS)} |",
        f"| Retrieval | {_shown(throughput['retrieval'], SHARE_DECIMALS)} |",
        "",
        "## Cycle and waiting times",
        "",
        "| Seconds | Mean | Median | 95th percentile | Maximum |",
        "|---|---|---|---|---|",
    ]
    for label, statistics in (("Order cycle time", cycle), ("Order waiting time", waiting)):
        values = " | ".join(
            _shown(statistics[name], TIME_DECIMALS) for name in ("mean", "median", "p95", "max")
        )
        lines.append(f"| {label} | {values} |")

    lines += [
        "",
        "## Crane utilization",
        "",
        "| Crane | Moving loaded | Moving empty | Handling | Idle |",
        "|---|---|---|---|---|",
    ]
    for crane, share in metrics["crane_utilization"].items():
        values = " | ".join(
            _shown(share[name], SHARE_DECIMALS)
            for name in ("moving_loaded", "moving_empty", "handling", "idle")
        )
        lines.append(f"| {crane} | {values} |")

    lines += [
        "",
        "## Backlog, occupancy, and order outcomes",
        "",
        f"- Backlog at window end: {backlog['at_window_end']} orders",
        f"- Highest backlog in window: {backlog['max_in_window']} orders",
        f"- Occupancy at window start: {_shown(occupancy['at_window_start'], SHARE_DECIMALS)}",
        f"- Occupancy at window end: {_shown(occupancy['at_window_end'], SHARE_DECIMALS)}",
        f"- Orders generated: {outcomes['generated']}",
        f"- Orders completed: {outcomes['completed']}",
        f"- Orders unfinished: {outcomes['unfinished']}",
        f"- Orders unfulfillable: {outcomes['unfulfillable']}",
        "",
        *_execution_lines(result),
        "## Metric definitions",
        "",
        "| Metric | Unit | Definition |",
        "|---|---|---|",
    ]
    lines += [
        f"| `{name}` | {entry['unit']} | {entry['definition']} |"
        for name, entry in result["definitions"].items()
    ]
    lines += ["", "## Modeling assumptions and simplifications", ""]
    lines += [f"- {assumption}" for assumption in result["assumptions"]]
    return "\n".join(lines) + "\n"


def _execution_lines(result: dict[str, Any]) -> list[str]:
    execution = result["run"].get("execution")
    if execution is None:
        return []
    controller = execution["controller"]
    hash_text = "" if controller["sha256"] is None else f" (SHA-256 `{controller['sha256']}`)"
    lines = [
        "## Execution",
        "",
        "- Mode: time_stepped",
        f"- Cycle time: {execution['cycle_ms']} ms",
        f"- Controller: {controller['name']}{hash_text}",
        f"- Signal list version: {execution['signal_list_version']}",
        "",
        *_plc_lines(result),
        "## Faults",
        "",
    ]
    if not result["faults"]:
        return [*lines, "There were no faults.", ""]
    lines += ["| Cycle | Time (s) | Crane | Fault | Description |", "|---|---|---|---|---|"]
    lines += [
        f"| {fault['cycle']} | {fault['time_s']} | {fault['crane']} | {fault['name']} "
        f"| {fault['description']} |"
        for fault in result["faults"]
    ]
    return [*lines, ""]


def _plc_lines(result: dict[str, Any]) -> list[str]:
    plc = result.get("plc")
    if plc is None:
        return []
    lines = [
        "## PLC",
        "",
        "This run is not reproducible, since it depends on a live PLC and on elapsed real time.",
        "",
        f"- Device: {plc['device']}",
        f"- Interface version: {plc['interface_version']}",
        f"- Stop reason: {plc['stop_reason']}",
        f"- Cycles: {plc['cycles']}",
        f"- Overrun cycles: {plc['overrun_cycles']}",
        f"- Slowest exchange: {plc['slowest_exchange_ms']} ms",
        f"- Simulated time: {plc['simulated_s']} s",
        f"- Elapsed real time: {plc['real_s']} s",
    ]
    if plc["stopped_at_cycle"] is not None:
        lines.append(f"- Stopped in cycle: {plc['stopped_at_cycle']}")
    if plc.get("warmup_skipped"):
        lines.append("- The run stopped during the warm-up, so the metrics cover all of it.")
    return [*lines, ""]


def orders_csv(orders: tuple[OrderRecord, ...]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(ORDER_COLUMNS)
    for order in orders:
        writer.writerow(
            (
                order.order_id,
                order.order_type,
                order.article,
                _csv_time(order.arrival_s),
                _csv_time(order.start_s),
                _csv_time(order.completion_s),
                "" if order.crane is None else order.crane,
                "" if order.location is None else "-".join(str(part) for part in order.location),
                order.transfer_point or "",
                order.outcome,
                order.reason,
            )
        )
    return buffer.getvalue()


def _csv_time(value: float | None) -> str:
    return "" if value is None else f"{value:.{TIME_DECIMALS}f}"
