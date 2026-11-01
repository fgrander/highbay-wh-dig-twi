from typing import Any

import pytest

from conftest import minimal_warehouse_dict
from highbay_sim.allocation import (
    FREE,
    OCCUPIED,
    RESERVED_FOR_RETRIEVAL,
    RESERVED_FOR_STORAGE,
    Allocation,
    cell_position,
    end_position,
)
from highbay_sim.config import WarehouseDefinition


def warehouse(
    stock: list[tuple[tuple[int, int, int, int], str]] | None = None,
    **layout: Any,
) -> WarehouseDefinition:
    content = minimal_warehouse_dict()
    content["layout"].update(layout)
    content["initial_stock"] = [
        {
            "location": dict(zip(("aisle", "rack", "bay", "level"), location, strict=True)),
            "article": article,
        }
        for location, article in stock or []
    ]
    return WarehouseDefinition.model_validate(content)


def random_warehouse(**layout: Any) -> WarehouseDefinition:
    return warehouse(**layout).model_copy(update={"storage_rule": "random_free"})


def test_cell_position_uses_bay_center_and_level_floor() -> None:
    layout = warehouse().layout
    assert cell_position(layout, (1, 1, 3, 2)) == (10.0, 3.0)
    assert cell_position(layout, (1, 1, 1, 1)) == (2.0, 0.0)


def test_aisle_ends_are_at_zero_and_full_length_at_ground_level() -> None:
    layout = warehouse().layout
    assert end_position(layout, "left") == (0.0, 0.0)
    assert end_position(layout, "right") == (20.0, 0.0)


def test_cell_states_follow_the_data_model() -> None:
    allocation = Allocation(warehouse(), seed=1)
    location = allocation.reserve_for_storage()
    assert location is not None
    assert allocation.state(location) == RESERVED_FOR_STORAGE
    allocation.store(location, "A")
    assert allocation.state(location) == OCCUPIED
    assert allocation.reserve_for_retrieval("A") == location
    assert allocation.state(location) == RESERVED_FOR_RETRIEVAL
    allocation.release(location)
    assert allocation.state(location) == FREE


def test_cell_count_includes_all_aisles_and_racks() -> None:
    assert Allocation(warehouse(aisle_count=2, racks_per_aisle=2), seed=1).cell_count == 40


def test_nearest_free_visits_cells_by_travel_time_from_inbound_point() -> None:
    allocation = Allocation(warehouse(), seed=1)
    order = [allocation.reserve_for_storage() for _ in range(10)]
    # Horizontal travel decides from bay 2 onwards, so levels of one bay tie.
    assert order == [
        (1, 1, 1, 1),
        (1, 1, 1, 2),
        (1, 1, 2, 1),
        (1, 1, 2, 2),
        (1, 1, 3, 1),
        (1, 1, 3, 2),
        (1, 1, 4, 1),
        (1, 1, 4, 2),
        (1, 1, 5, 1),
        (1, 1, 5, 2),
    ]
    assert allocation.reserve_for_storage() is None


def test_nearest_free_breaks_ties_in_location_order() -> None:
    allocation = Allocation(warehouse(aisle_count=2, racks_per_aisle=2), seed=1)
    first_four = [allocation.reserve_for_storage() for _ in range(4)]
    assert first_four == [(1, 1, 1, 1), (1, 2, 1, 1), (2, 1, 1, 1), (2, 2, 1, 1)]


def test_nearest_free_considers_all_aisles() -> None:
    stock = [((1, 1, 1, 1), "B")]
    allocation = Allocation(warehouse(stock, aisle_count=2), seed=1)
    assert allocation.reserve_for_storage() == (2, 1, 1, 1)


def test_nearest_free_measures_from_inbound_point_of_the_cells_aisle() -> None:
    content = minimal_warehouse_dict()
    content["layout"]["aisle_count"] = 2
    content["transfer_points"]["aisles"] = {
        2: {"left": ["outbound"], "right": ["inbound"]},
    }
    allocation = Allocation(WarehouseDefinition.model_validate(content), seed=1)
    # Bay 1 of aisle 1 and bay 5 of aisle 2 are both 2 m from an inbound point.
    assert [allocation.reserve_for_storage() for _ in range(2)] == [(1, 1, 1, 1), (2, 1, 5, 1)]


def test_released_cell_can_be_reserved_again() -> None:
    stock = [((1, 1, b, lv), "B") for b in range(1, 6) for lv in range(1, 3)]
    allocation = Allocation(warehouse(stock), seed=1)
    assert allocation.reserve_for_storage() is None
    location = allocation.reserve_for_retrieval("B")
    assert location is not None
    assert allocation.reserve_for_storage() is None
    allocation.release(location)
    assert allocation.reserve_for_storage() == location


def test_stock_cells_are_not_free() -> None:
    stock = [((1, 1, 1, 1), "B")]
    allocation = Allocation(warehouse(stock), seed=1)
    assert allocation.state((1, 1, 1, 1)) == OCCUPIED
    assert allocation.reserve_for_storage() != (1, 1, 1, 1)


def test_random_free_is_reproducible_for_a_seed() -> None:
    def sequence(seed: int) -> list[Any]:
        allocation = Allocation(random_warehouse(aisle_count=2, racks_per_aisle=2), seed=seed)
        return [allocation.reserve_for_storage() for _ in range(40)]

    assert sequence(3) == sequence(3)
    assert sequence(3) != sequence(4)
    assert sorted(sequence(3)) == sorted(sequence(4))


def test_random_free_considers_all_aisles() -> None:
    allocation = Allocation(random_warehouse(aisle_count=3), seed=1)
    chosen = [allocation.reserve_for_storage() for _ in range(30)]
    assert {location[0] for location in chosen if location} == {1, 2, 3}


def test_random_free_cell_is_available_after_release() -> None:
    allocation = Allocation(random_warehouse(), seed=1)
    chosen = [allocation.reserve_for_storage() for _ in range(10)]
    assert allocation.reserve_for_storage() is None
    location = chosen[4]
    assert location is not None
    allocation.store(location, "A")
    assert allocation.reserve_for_retrieval("A") == location
    allocation.release(location)
    assert allocation.reserve_for_storage() == location


def test_retrieval_takes_oldest_stock_across_aisles() -> None:
    stock = [((2, 1, 1, 1), "A"), ((1, 1, 2, 1), "A")]
    allocation = Allocation(warehouse(stock, aisle_count=2), seed=1)
    # Initial stock has equal age, so location order decides.
    assert allocation.reserve_for_retrieval("A") == (1, 1, 2, 1)
    assert allocation.reserve_for_retrieval("A") == (2, 1, 1, 1)


def test_stored_stock_is_newer_than_initial_stock() -> None:
    stock = [((1, 1, 5, 1), "A")]
    allocation = Allocation(warehouse(stock), seed=1)
    location = allocation.reserve_for_storage()
    assert location is not None
    allocation.store(location, "A")
    assert allocation.reserve_for_retrieval("A") == (1, 1, 5, 1)
    assert allocation.reserve_for_retrieval("A") == location


def test_retrieval_without_stock_returns_none() -> None:
    allocation = Allocation(warehouse([((1, 1, 1, 1), "B")]), seed=1)
    assert allocation.reserve_for_retrieval("A") is None


def test_reserved_stock_is_unavailable_to_other_orders() -> None:
    allocation = Allocation(warehouse([((1, 1, 1, 1), "A")]), seed=1)
    assert allocation.reserve_for_retrieval("A") == (1, 1, 1, 1)
    assert allocation.reserve_for_retrieval("A") is None


def test_stock_in_reserved_cell_is_not_available_until_stored() -> None:
    allocation = Allocation(warehouse(), seed=1)
    location = allocation.reserve_for_storage()
    assert allocation.reserve_for_retrieval("A") is None
    assert location is not None
    allocation.store(location, "A")
    assert allocation.reserve_for_retrieval("A") == location


def test_invalid_state_transition_is_an_error() -> None:
    allocation = Allocation(warehouse(), seed=1)
    with pytest.raises(ValueError):
        allocation.release((1, 1, 1, 1))
