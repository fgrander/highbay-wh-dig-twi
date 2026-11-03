"""What the window says about a state and a selection, as in the browser viewer's panels."""

from test_core_recorded_source import CELL, STOCK_CELL, event, source, storage_events

from highbay.replay.core.display_text import (
    cell_details,
    crane_details,
    figure_lines,
    load_details,
    run_identification,
)


def test_figures_at_a_time() -> None:
    instance = source(storage_events())
    state = instance.state_at(1.5)
    assert figure_lines(state) == [
        "Warm-up",
        "Backlog: 1",
        "Aisle 1: 1",
        "Waiting for a cell: 0",
        "Occupancy: 0.050000",
        "Completed: 0",
        "Unfulfillable: 0",
    ]
    assert figure_lines(instance.state_at(40.0))[0] == "Measurement window"
    assert figure_lines(instance.state_at(40.0))[4] == "Occupancy: 0.100000"


def test_run_identification() -> None:
    assert run_identification(source().describe()) == [
        "Warehouse: w",
        "Scenario: s",
        "Seed: 1",
        "Software version: 0.4.0",
    ]


def test_run_identification_without_a_recording_says_nothing() -> None:
    description = source().describe()
    assert (
        run_identification(
            type(description)(
                **{
                    "layout": description.layout,
                    "crane": description.crane,
                    "transfer_points": description.transfer_points,
                    "crane_start_positions": description.crane_start_positions,
                    "articles": description.articles,
                }
            )
        )
        == []
    )


def test_idle_crane() -> None:
    instance = source()
    assert crane_details(instance, instance.state_at(0.0), 1) == ["Crane 1", "Activity: idle"]


def test_crane_moving_a_load_to_its_cell() -> None:
    instance = source(storage_events())
    assert crane_details(instance, instance.state_at(15.0), 1) == [
        "Crane 1",
        "Activity: moving loaded",
        "Order: O1",
        "Destination: cell 1-1-3-2",
        "Carrying: a",
    ]


def test_crane_going_to_an_aisle_end_for_a_storage_order() -> None:
    instance = source(
        [
            event(
                2.0,
                "activity_started",
                order=0,
                crane=1,
                activity="moving_empty",
                end_s=9.0,
                start_position=[8.0, 0.0],
                target_position=[0.0, 0.0],
            )
        ]
    )
    assert crane_details(instance, instance.state_at(3.0), 1) == [
        "Crane 1",
        "Activity: moving empty",
        "Order: O1",
        "Destination: left end",
    ]


def test_load_unit_from_initial_stock() -> None:
    instance = source()
    instance.state_at(0.0)
    assert load_details(instance, "i0") == [
        "Load unit: b",
        "Origin: initial stock",
        "Cell: 1-2-1-1",
        "Cell state: occupied",
    ]


def test_load_unit_on_a_crane_shows_its_order() -> None:
    instance = source(storage_events())
    instance.state_at(15.0)
    assert load_details(instance, "o0") == [
        "Load unit: a",
        "Storage order: O1",
        "Arrival: 1.000 s",
        "Start: 2.000 s",
        "Completion: 40.000 s",
        "On: Crane 1",
    ]


def test_load_unit_with_a_retrieval_order_and_missing_times() -> None:
    instance = source([event(3.0, "order_queued", order=1, crane=1, location=list(STOCK_CELL))])
    instance.state_at(3.0)
    assert load_details(instance, "i0") == [
        "Load unit: b",
        "Origin: initial stock",
        "Retrieval order: O2",
        "Arrival: 3.000 s",
        "Start: not available",
        "Completion: not available",
        "Cell: 1-2-1-1",
        "Cell state: reserved_for_retrieval",
    ]


def test_cell() -> None:
    instance = source()
    instance.state_at(0.0)
    assert cell_details(instance, tuple(CELL)) == ["Cell: 1-1-3-2", "Cell state: free"]


def describe_load(article: int) -> str | None:
    return {0: "board 2.1 m + board 3.5 m", 1: None}[article]


def test_details_of_a_stored_load_say_what_it_is_after_the_article() -> None:
    instance = source()
    instance.state_at(0.0)
    plain = load_details(instance, "i0")
    described = load_details(instance, "i0", lambda _article: "paper")
    assert described[0] == plain[0]
    assert described[1] == "Load: paper"
    assert described[2:] == plain[1:]


def test_details_of_an_undefined_article_stay_as_they_were() -> None:
    instance = source()
    instance.state_at(0.0)
    assert load_details(instance, "i0", lambda _article: None) == load_details(instance, "i0")


def test_details_of_a_crane_say_what_it_carries() -> None:
    instance = source(storage_events())
    state = instance.state_at(15.0)
    plain = crane_details(instance, state, 1)
    described = crane_details(instance, state, 1, describe_load)
    assert described[: len(plain)] == plain
    assert described[len(plain) :] == ["Load: board 2.1 m + board 3.5 m"]
