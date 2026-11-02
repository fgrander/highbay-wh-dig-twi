"""SC-004: the viewer's crane positions compared with values calculated by hand.

The warehouse has horizontal speed 2 m/s and acceleration 1 m/s², and vertical speed 1 m/s and
acceleration 1 m/s². The storage order's loaded movement runs from (0, 0) at 10 s to (10, 3) at
17 s.

Horizontal, 10 m: 2 s accelerating (2 m), 3 s at full speed (6 m), and 2 s braking (2 m).
Vertical, 3 m: 1 s accelerating (0.5 m), 2 s at full speed (2 m), 1 s braking (0.5 m), so it
finishes after 4 s and holds its target.
"""

from collections.abc import Callable
from pathlib import Path

import pytest
from playwright.sync_api import Page

from conftest import SAMPLES

TOLERANCE_M = 0.01
VERIFICATION = SAMPLES / "verification"
CELL = [1, 1, 3, 2]


@pytest.fixture
def viewer(page: Page, serve: Callable[[Path], str], write_run: Callable[..., Path]) -> Page:
    output = write_run(VERIFICATION / "v1-warehouse.yaml", VERIFICATION / "v1-scenario.yaml")
    page.goto(serve(output / "replay.json"))
    page.wait_for_function("window.highbayViewer !== undefined")
    page.evaluate("window.highbayViewer.ready")
    return page


def move_to(page: Page, time_s: float) -> None:
    page.locator("#time-slider").fill(f"{time_s:g}")


@pytest.mark.parametrize(
    ("time_s", "horizontal", "vertical"),
    [
        (10.0, 0.0, 0.0),
        (11.0, 0.5, 0.5),  # 1·1²/2 on both axes
        (12.0, 2.0, 1.5),  # horizontal 2·... accelerated 2 m; vertical 0.5 + 1
        (13.0, 4.0, 2.5),  # horizontal 2 + 2; vertical 0.5 + 2
        (14.0, 6.0, 3.0),  # horizontal 2 + 4; vertical finished
        (15.0, 8.0, 3.0),  # horizontal 2 + 6
        (16.0, 9.5, 3.0),  # horizontal 10 - 1·1²/2
        (17.0, 10.0, 3.0),
    ],
)
def test_crane_position(viewer: Page, time_s: float, horizontal: float, vertical: float) -> None:
    move_to(viewer, time_s)
    position = viewer.evaluate("window.highbayViewer.crane(1).position")
    assert position[0] == pytest.approx(horizontal, abs=TOLERANCE_M)
    assert position[1] == pytest.approx(vertical, abs=TOLERANCE_M)


def test_retrieval_movement_to_the_right_end(viewer: Page) -> None:
    # From (10, 3) at 40 s to (20, 0) at 47 s, with the same profiles.
    move_to(viewer, 42.0)
    position = viewer.evaluate("window.highbayViewer.crane(1).position")
    assert position[0] == pytest.approx(12.0, abs=TOLERANCE_M)
    assert position[1] == pytest.approx(1.5, abs=TOLERANCE_M)
    move_to(viewer, 47.0)
    position = viewer.evaluate("window.highbayViewer.crane(1).position")
    assert position == pytest.approx([20.0, 0.0], abs=TOLERANCE_M)


@pytest.mark.parametrize(
    ("time_s", "on_crane", "in_cell"),
    [
        (9.9, False, False),
        (10.0, True, False),
        (26.9, True, False),
        (27.0, False, True),
        (39.9, False, True),
        (40.0, True, False),
        (56.9, True, False),
        (57.0, False, False),
    ],
)
def test_load_unit_times(viewer: Page, time_s: float, on_crane: bool, in_cell: bool) -> None:
    move_to(viewer, time_s)
    assert (viewer.evaluate("window.highbayViewer.crane(1).carrying") is not None) == on_crane
    cell = viewer.evaluate(f"window.highbayViewer.cell({CELL})")
    assert (cell["load"] is not None) == in_cell
