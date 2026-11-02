"""Navigation and inspection through the viewer's interface."""

import csv
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from playwright.sync_api import Page

from conftest import SAMPLES, minimal_scenario_dict, minimal_warehouse_dict, write_yaml

VERIFICATION = SAMPLES / "verification"
V1_CELL = [1, 1, 3, 2]


def open_viewer(page: Page, address: str) -> None:
    page.goto(address)
    page.wait_for_function("window.highbayViewer !== undefined")
    page.evaluate("window.highbayViewer.ready")


def hook(page: Page, expression: str) -> Any:
    return page.evaluate(f"window.highbayViewer.{expression}")


def move_to(page: Page, time_s: float) -> None:
    page.locator("#time-slider").fill(f"{time_s:g}")


def click_at(page: Page, point: list[float]) -> None:
    page.mouse.click(point[0], point[1])


def details(page: Page) -> str:
    return page.locator("#details").inner_text()


@pytest.fixture
def v1_output(write_run: Callable[..., Path]) -> Path:
    return write_run(VERIFICATION / "v1-warehouse.yaml", VERIFICATION / "v1-scenario.yaml")


@pytest.fixture
def v1(page: Page, serve: Callable[[Path], str], v1_output: Path) -> Page:
    open_viewer(page, serve(v1_output / "replay.json"))
    return page


def drag_in_view(page: Page, button: str = "left") -> None:
    box = page.locator("#view canvas").bounding_box()
    assert box is not None
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    page.mouse.move(x, y)
    page.mouse.down(button=button)
    page.mouse.move(x + 120, y + 40, steps=4)
    page.mouse.up(button=button)


def test_rotating_moving_and_zooming_change_only_the_camera(v1: Page) -> None:
    move_to(v1, 13)
    before = hook(v1, "summary()")
    camera = hook(v1, "cameraPosition()")

    drag_in_view(v1)
    rotated = hook(v1, "cameraPosition()")
    assert rotated != camera

    drag_in_view(v1, "right")
    moved = hook(v1, "cameraPosition()")
    assert moved != rotated

    box = v1.locator("#view canvas").bounding_box()
    assert box is not None
    v1.mouse.move(box["x"] + 100, box["y"] + 100)
    v1.mouse.wheel(0, -300)
    v1.wait_for_function(
        "(previous) => JSON.stringify(window.highbayViewer.cameraPosition())"
        " !== JSON.stringify(previous)",
        arg=moved,
    )

    assert hook(v1, "summary()") == before
    assert hook(v1, "playing") is False
    assert hook(v1, "selection") is None


def test_camera_movement_does_not_interrupt_playback(v1: Page) -> None:
    v1.locator("#speed").select_option("10")
    v1.locator("#play").click()
    drag_in_view(v1)
    assert hook(v1, "playing") is True


def test_default_view_shows_the_whole_warehouse_again(v1: Page) -> None:
    box = v1.locator("#view canvas").bounding_box()
    assert box is not None
    v1.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    for _ in range(8):
        v1.mouse.wheel(0, -500)
    v1.wait_for_function("window.highbayViewer.boundsInView() === false")
    v1.locator("#default-view").click()
    assert hook(v1, "boundsInView()") is True


def test_selecting_a_crane_shows_its_details(v1: Page) -> None:
    move_to(v1, 13)
    click_at(v1, hook(v1, "craneScreenPosition(1)"))
    assert hook(v1, "selection") == {"kind": "crane", "aisle": 1}
    text = details(v1)
    assert "Crane 1" in text
    assert "moving loaded" in text
    assert "O000001" in text
    assert "cell 1-1-3-2" in text


def test_crane_details_refresh_as_time_changes(v1: Page) -> None:
    move_to(v1, 13)
    click_at(v1, hook(v1, "craneScreenPosition(1)"))
    move_to(v1, 20)
    assert "handling" in details(v1)
    move_to(v1, 42)
    text = details(v1)
    assert "O000002" in text
    assert "right end" in text
    move_to(v1, 28)
    text = details(v1)
    assert "idle" in text
    assert "O00000" not in text


def test_moving_empty_to_a_transfer_point_names_it(
    page: Page,
    serve: Callable[[Path], str],
    write_run: Callable[..., Path],
    tmp_path: Path,
) -> None:
    # After a retrieval leaves the crane at the right end, it returns empty to the left end.
    scenario = minimal_scenario_dict()
    scenario["orders"] = [
        {"time_s": 0, "type": "retrieval", "article": "B"},
        {"time_s": 200, "type": "storage", "article": "C"},
    ]
    warehouse = minimal_warehouse_dict()
    warehouse["initial_stock"] = [
        {"location": {"aisle": 1, "rack": 1, "bay": 1, "level": 1}, "article": "B"}
    ]
    output = write_run(
        write_yaml(tmp_path / "w.yaml", warehouse), write_yaml(tmp_path / "s.yaml", scenario)
    )
    open_viewer(page, serve(output / "replay.json"))
    move_to(page, 202)
    click_at(page, hook(page, "craneScreenPosition(1)"))
    text = details(page)
    assert "moving empty" in text
    assert "left end" in text


def test_clicking_an_occupied_cell_selects_its_load_unit_and_shows_the_cell(v1: Page) -> None:
    click_at(v1, hook(v1, "cellScreenPosition([1, 1, 2, 2])"))
    selection = hook(v1, "selection")
    assert selection["kind"] == "load"
    text = details(v1)
    assert "B" in text
    assert "initial stock" in text
    assert "1-1-2-2" in text
    assert "occupied" in text


def test_load_unit_details_match_the_order_file(v1: Page, v1_output: Path) -> None:
    rows = list(csv.DictReader((v1_output / "orders.csv").read_text("utf-8").splitlines()))
    move_to(v1, 28)
    click_at(v1, hook(v1, f"cellScreenPosition({V1_CELL})"))
    text = details(v1)
    assert hook(v1, "selection")["kind"] == "load"
    assert rows[0]["order_id"] in text
    assert rows[0]["article"] in text
    assert rows[0]["arrival_s"] in text
    assert rows[0]["start_s"] in text
    assert rows[0]["completion_s"] in text


def test_clicking_an_empty_cell_selects_the_cell(
    page: Page,
    serve: Callable[[Path], str],
    write_run: Callable[..., Path],
    tmp_path: Path,
) -> None:
    output = write_run(
        write_yaml(tmp_path / "w.yaml", minimal_warehouse_dict()),
        write_yaml(tmp_path / "s.yaml", minimal_scenario_dict()),
    )
    open_viewer(page, serve(output / "replay.json"))
    click_at(page, hook(page, f"cellScreenPosition({V1_CELL})"))
    selection = hook(page, "selection")
    assert selection["kind"] == "cell"
    text = details(page)
    assert "-".join(str(part) for part in selection["location"]) in text
    assert "free" in text


def test_load_unit_on_a_crane_can_be_selected_through_its_details(v1: Page) -> None:
    move_to(v1, 13)
    click_at(v1, hook(v1, "craneScreenPosition(1)"))
    v1.locator("#select-carried").click()
    assert hook(v1, "selection") == {"kind": "load", "key": "o0"}
    text = details(v1)
    assert "A" in text
    assert "O000001" in text
    assert "Crane 1" in text


def test_no_carried_load_gives_no_selection_button(v1: Page) -> None:
    move_to(v1, 28)
    click_at(v1, hook(v1, "craneScreenPosition(1)"))
    assert v1.locator("#select-carried").count() == 0


def test_selected_load_unit_follows_and_clears_when_it_no_longer_exists(v1: Page) -> None:
    move_to(v1, 28)
    click_at(v1, hook(v1, f"cellScreenPosition({V1_CELL})"))
    selection = hook(v1, "selection")
    assert selection == {"kind": "load", "key": "o0"}

    move_to(v1, 45)
    assert hook(v1, "selection") == selection
    assert "Crane 1" in details(v1)

    move_to(v1, 57)
    assert hook(v1, "selection") is None
    assert details(v1) == ""


def test_selection_clears_when_moving_before_the_load_unit_existed(v1: Page) -> None:
    move_to(v1, 28)
    click_at(v1, hook(v1, f"cellScreenPosition({V1_CELL})"))
    move_to(v1, 5)
    assert hook(v1, "selection") is None


def test_clicking_elsewhere_clears_the_selection(v1: Page) -> None:
    click_at(v1, hook(v1, "cellScreenPosition([1, 1, 1, 1])"))
    assert hook(v1, "selection") is not None
    box = v1.locator("#view canvas").bounding_box()
    assert box is not None
    v1.mouse.click(box["x"] + 5, box["y"] + 5)
    assert hook(v1, "selection") is None
    assert details(v1) == ""


def test_dragging_does_not_change_the_selection(v1: Page) -> None:
    click_at(v1, hook(v1, "cellScreenPosition([1, 1, 1, 1])"))
    selection = hook(v1, "selection")
    drag_in_view(v1)
    assert hook(v1, "selection") == selection
