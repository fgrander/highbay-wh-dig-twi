"""The order rules shared by the event-based and the time-stepped simulation."""

from typing import Any

from conftest import minimal_warehouse_dict
from highbay_sim.config import WarehouseDefinition
from highbay_sim.events import OrderType
from highbay_sim.order_handling import OrderHandling, OrderRecord
from highbay_sim.orders import OrderRequest

LEFT = (0.0, 0.0)
RIGHT = (20.0, 0.0)
ALL_CELLS = [(1, 1, bay, level) for bay in range(1, 6) for level in range(1, 3)]
Stock = dict[tuple[int, int, int, int], str]


def warehouse(
    stock: Stock | None = None,
    default: dict[str, list[str]] | None = None,
    aisle_count: int = 1,
) -> WarehouseDefinition:
    content = minimal_warehouse_dict()
    content["layout"]["aisle_count"] = aisle_count
    if default is not None:
        content["transfer_points"]["default"] = default
    content["initial_stock"] = [
        {
            "location": dict(zip(("aisle", "rack", "bay", "level"), location, strict=True)),
            "article": article,
        }
        for location, article in (stock or {}).items()
    ]
    return WarehouseDefinition.model_validate(content)


class Recorder:
    def __init__(self, wh: WarehouseDefinition) -> None:
        self.emitted: list[tuple[str, str]] = []
        self.queued: list[int] = []
        self.handling = OrderHandling(wh, 1, self.emit, self.queued.append)

    def emit(self, kind: Any, order: OrderRecord, location: Any = None) -> None:
        self.emitted.append((kind, order.order_id))

    def arrive(self, time_s: float, order_type: OrderType, article: str) -> OrderRecord:
        self.handling.arrive(OrderRequest(time_s, order_type, article))
        return self.handling.orders[-1]


def test_order_receives_its_cell_on_arrival() -> None:
    recorder = Recorder(warehouse())
    order = recorder.arrive(1.5, "storage", "A")
    assert order.order_id == "O000001"
    assert order.arrival_s == 1.5
    assert order.location == (1, 1, 1, 1)
    assert order.crane == 1
    assert recorder.queued == [1]
    assert recorder.emitted == [("order_arrived", "O000001"), ("order_queued", "O000001")]


def test_orders_are_first_come_first_served_per_aisle() -> None:
    recorder = Recorder(warehouse({(1, 1, 1, 1): "A", (2, 1, 1, 1): "B"}, aisle_count=2))
    first = recorder.arrive(0.0, "retrieval", "A")
    other_aisle = recorder.arrive(1.0, "retrieval", "B")
    assert recorder.handling.next_order(1) is first
    assert recorder.handling.next_order(1) is None
    assert recorder.handling.next_order(2) is other_aisle


def test_storage_without_a_free_cell_waits_and_gets_a_released_cell() -> None:
    stock: Stock = {location: "B" for location in ALL_CELLS}
    recorder = Recorder(warehouse(stock))
    retrieval = recorder.arrive(0.0, "retrieval", "B")
    waiting = recorder.arrive(1.0, "storage", "A")
    assert waiting.location is None
    assert ("order_waiting_for_cell", waiting.order_id) in recorder.emitted
    recorder.handling.finish_pick(retrieval)
    assert waiting.location == retrieval.location
    assert ("load_picked", retrieval.order_id) in recorder.emitted
    assert ("order_queued", waiting.order_id) in recorder.emitted


def test_retrieval_without_stock_is_unfulfillable() -> None:
    recorder = Recorder(warehouse())
    order = recorder.arrive(0.0, "retrieval", "A")
    assert (order.outcome, order.reason) == ("unfulfillable", "no_stock")
    assert recorder.queued == []


def test_stock_counts_only_after_set_down() -> None:
    recorder = Recorder(warehouse())
    storage = recorder.arrive(0.0, "storage", "A")
    assert recorder.arrive(1.0, "retrieval", "A").outcome == "unfulfillable"
    recorder.handling.finish_set(storage)
    assert recorder.arrive(2.0, "retrieval", "A").outcome == "unfinished"


def test_storage_uses_the_inbound_end_with_lowest_total_travel() -> None:
    both = {"left": ["inbound"], "right": ["inbound", "outbound"]}
    recorder = Recorder(warehouse(default=both))
    order = recorder.arrive(0.0, "storage", "A")
    # The cell is 2 m from the left end. From 1 m, the left end is nearer on both legs.
    first, second = recorder.handling.plan_transport(order, (1.0, 0.0))
    assert first == LEFT
    assert second == (2.0, 0.0)
    assert order.transfer_point == "left"


def test_storage_tie_uses_the_left_end() -> None:
    both = {"left": ["inbound"], "right": ["inbound", "outbound"]}
    recorder = Recorder(warehouse(default=both))
    order = recorder.arrive(0.0, "storage", "A")
    # From 18 m, via the left end is 18 m then 2 m, and via the right end is 2 m then 18 m.
    assert recorder.handling.plan_transport(order, (18.0, 0.0))[0] == LEFT


def test_retrieval_uses_the_nearer_outbound_end() -> None:
    both = {"left": ["inbound", "outbound"], "right": ["outbound"]}
    recorder = Recorder(warehouse({(1, 1, 5, 1): "A"}, default=both))
    order = recorder.arrive(0.0, "retrieval", "A")
    first, second = recorder.handling.plan_transport(order, LEFT)
    assert first == (18.0, 0.0)
    assert second == RIGHT
    assert order.transfer_point == "right"


def test_retrieval_tie_uses_the_left_end() -> None:
    both = {"left": ["inbound", "outbound"], "right": ["outbound"]}
    recorder = Recorder(warehouse({(1, 1, 3, 1): "A"}, default=both))
    order = recorder.arrive(0.0, "retrieval", "A")
    assert recorder.handling.plan_transport(order, LEFT)[1] == LEFT


def test_final_reasons_of_open_orders() -> None:
    stock: Stock = {location: "B" for location in ALL_CELLS}
    recorder = Recorder(warehouse(stock))
    queued = recorder.arrive(0.0, "retrieval", "B")
    waiting = recorder.arrive(1.0, "storage", "A")
    recorder.handling.set_final_reasons()
    assert queued.reason == "run_ended"
    assert waiting.reason == "no_free_cell"
