"""SC-003 and SC-008 at the planning target. SC-002, the frame rate, needs real graphics hardware.

Moving to a time is measured in headless Chromium, and includes updating the scene and all figures,
but not drawing, which depends on the graphics hardware.
"""

import json
import random
from collections.abc import Callable
from pathlib import Path

import pytest
from playwright.sync_api import Page
from write_planning_target import write_planning_target

MAX_REPLAY_BYTES = 100_000_000
MAX_REPLAY_WRITE_S = 30.0
MAX_MOVE_S = 1.0


@pytest.fixture(scope="module")
def target(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, float]:
    directory = tmp_path_factory.mktemp("planning-target")
    return directory, write_planning_target(directory).replay_s


@pytest.mark.performance
def test_replay_data_size_and_writing_time(target: tuple[Path, float]) -> None:
    directory, replay_write_s = target
    assert (directory / "replay.json").stat().st_size <= MAX_REPLAY_BYTES
    assert replay_write_s <= MAX_REPLAY_WRITE_S


@pytest.mark.performance
@pytest.mark.viewer
def test_moving_to_any_time_is_fast_and_correct(
    target: tuple[Path, float], page: Page, serve: Callable[[Path], str]
) -> None:
    directory, _ = target
    data = json.loads((directory / "replay.json").read_text(encoding="utf-8"))
    duration = data["run"]["duration_s"]
    generator = random.Random(1)
    times = [duration, 0.0, *(generator.uniform(0.0, duration) for _ in range(20))]

    page.goto(serve(directory / "replay.json"), timeout=120_000)
    page.wait_for_function("window.highbayViewer !== undefined")
    page.evaluate("window.highbayViewer.ready")
    assert page.evaluate("window.highbayViewer.lastError") is None

    results = page.evaluate(
        """(times) => times.map((time) => {
            const slider = document.querySelector('#time-slider');
            const start = performance.now();
            slider.value = String(time);
            slider.dispatchEvent(new Event('input'));
            const summary = window.highbayViewer.summary();
            const elapsed = performance.now() - start;
            return { elapsed, summary, drawn: window.highbayViewer.sceneInfo().load_units };
        })""",
        times,
    )

    for result in results:
        assert result["elapsed"] / 1000 < MAX_MOVE_S
        assert result["drawn"] == result["summary"]["occupied_cells"]

    at_end, at_start = results[0]["summary"], results[1]["summary"]
    outcomes = data["reported"]["order_outcomes"]
    assert at_end["completed"] == outcomes["completed"]
    assert at_end["unfulfillable"] == outcomes["unfulfillable"]
    assert at_end["backlog"]["total"] == data["reported"]["backlog_orders"]["at_window_end"]
    assert round(at_end["occupancy"], 6) == data["reported"]["storage_occupancy"]["at_window_end"]
    assert at_start["occupied_cells"] == len(data["initial_stock"])
