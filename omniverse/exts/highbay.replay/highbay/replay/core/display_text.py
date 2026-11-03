"""What the window says about a state and a selection, as in the browser viewer's panels."""

from collections.abc import Callable

from .state_source import (
    CraneState,
    Location,
    OrderDetails,
    RunState,
    StateSource,
    WarehouseDescription,
)

OCCUPANCY_DECIMALS = 6

# Says what an article's load is, by the index of the article, or None if nothing is defined.
LoadDescription = Callable[[int], str | None]


def _location_text(location: Location) -> str:
    return "-".join(str(part) for part in location)


def _time_text(value: float | None) -> str:
    return "not available" if value is None else f"{value:.3f} s"


def figure_lines(state: RunState) -> list[str]:
    return [
        "Measurement window" if state.in_measurement_window else "Warm-up",
        f"Backlog: {state.backlog.total}",
        *(f"Aisle {aisle}: {count}" for aisle, count in state.backlog.per_aisle.items()),
        f"Waiting for a cell: {state.backlog.waiting_for_cell}",
        f"Occupancy: {state.occupancy:.{OCCUPANCY_DECIMALS}f}",
        f"Completed: {state.completed}",
        f"Unfulfillable: {state.unfulfillable}",
    ]


def run_identification(description: WarehouseDescription) -> list[str]:
    run = description.run
    if not run:
        return []
    return [
        f"Warehouse: {run['warehouse']['name']}",
        f"Scenario: {run['scenario']['name']}",
        f"Seed: {run['seed']}",
        f"Software version: {run['software_version']}",
    ]


def _crane_destination(crane: CraneState, order: OrderDetails) -> str | None:
    if crane.movement_target is None:
        return None
    goes_to_cell = (order.type == "storage") == (crane.activity == "moving_loaded")
    if goes_to_cell and order.location is not None:
        return f"cell {_location_text(order.location)}"
    return f"{order.end} end"


def _load_line(describe_load: LoadDescription | None, article: int) -> list[str]:
    described = describe_load(article) if describe_load else None
    return [f"Load: {described}"] if described else []


def crane_details(
    source: StateSource, state: RunState, aisle: int, describe_load: LoadDescription | None = None
) -> list[str]:
    crane = state.cranes[aisle]
    lines = [f"Crane {aisle}", f"Activity: {crane.activity.replace('_', ' ')}"]
    if crane.order is not None:
        order = source.order(crane.order)
        lines.append(f"Order: {order.order_id}")
        destination = _crane_destination(crane, order)
        if destination:
            lines.append(f"Destination: {destination}")
    if crane.carrying is not None:
        load = source.load(crane.carrying)
        if load is not None:
            lines.append(f"Carrying: {source.describe().articles[load.article]}")
            lines += _load_line(describe_load, load.article)
    return lines


def _order_lines(source: StateSource, label: str, index: int) -> list[str]:
    order = source.order(index)
    return [
        f"{label}: {order.order_id}",
        f"Arrival: {_time_text(order.arrival_s)}",
        f"Start: {_time_text(order.start_s)}",
        f"Completion: {_time_text(order.completion_s)}",
    ]


def load_details(
    source: StateSource, key: str, describe_load: LoadDescription | None = None
) -> list[str]:
    load = source.load(key)
    if load is None:
        return []
    lines = [f"Load unit: {source.describe().articles[load.article]}"]
    lines += _load_line(describe_load, load.article)
    if load.store_order is None:
        lines.append("Origin: initial stock")
    else:
        lines += _order_lines(source, "Storage order", load.store_order)
    if load.retrieve_order is not None:
        lines += _order_lines(source, "Retrieval order", load.retrieve_order)
    if load.location is not None:
        lines += cell_details(source, load.location)
    else:
        lines.append(f"On: Crane {load.crane}")
    return lines


def cell_details(source: StateSource, location: Location) -> list[str]:
    cell = source.cell(location)
    return [f"Cell: {_location_text(cell.location)}", f"Cell state: {cell.state}"]
