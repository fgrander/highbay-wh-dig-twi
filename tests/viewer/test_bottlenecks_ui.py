"""Spotting bottlenecks: crane colors, figures, and the jump to the highest backlog."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from playwright.sync_api import Page

from conftest import SAMPLES, replay_data

OVERLOADED = SAMPLES / "replay" / "overloaded-warehouse.yaml"
BUSY = SAMPLES / "replay" / "busy-scenario.yaml"
VERIFICATION = SAMPLES / "verification"
ACTIVITY_COLORS = {
    "moving_empty": "#2f6fd6",
    "moving_loaded": "#e8842c",
    "handling": "#8a4fc7",
    "idle": "#8a8f96",
}


def open_viewer(page: Page, address: str) -> None:
    page.goto(address)
    page.wait_for_function("window.highbayViewer !== undefined")
    page.evaluate("window.highbayViewer.ready")


def hook(page: Page, expression: str) -> Any:
    return page.evaluate(f"window.highbayViewer.{expression}")


def move_to(page: Page, time_s: float) -> None:
    """Move to an exact time, which typing into the slider would round."""
    page.evaluate(
        """(time) => {
            const slider = document.querySelector('#time-slider');
            slider.value = String(time);
            slider.dispatchEvent(new Event('input'));
        }""",
        time_s,
    )


def figure(page: Page, name: str) -> str:
    return page.locator(f"#figure-{name}").inner_text()


@pytest.fixture
def overloaded_output(write_run: Callable[..., Path]) -> Path:
    return write_run(OVERLOADED, BUSY)


@pytest.fixture
def overloaded(page: Page, serve: Callable[[Path], str], overloaded_output: Path) -> Page:
    open_viewer(page, serve(overloaded_output / "replay.json"))
    return page


@pytest.fixture
def v1(page: Page, serve: Callable[[Path], str], write_run: Callable[..., Path]) -> Page:
    output = write_run(VERIFICATION / "v1-warehouse.yaml", VERIFICATION / "v3-scenario.yaml")
    open_viewer(page, serve(output / "replay.json"))
    return page


@pytest.mark.parametrize(
    ("time_s", "activity"),
    [
        (5.0, "handling"),
        (13.0, "moving_loaded"),
        (28.0, "idle"),
    ],
)
def test_crane_color_shows_its_activity(v1: Page, time_s: float, activity: str) -> None:
    move_to(v1, time_s)
    assert hook(v1, "craneColor(1)") == ACTIVITY_COLORS[activity]


def test_crane_color_when_moving_empty(overloaded: Page, overloaded_output: Path) -> None:
    rows = replay_data(overloaded_output)["events"]
    row = next(r for r in rows if r[5] == "moving_empty" and r[6] > r[0] + 1)
    move_to(overloaded, (row[0] + row[6]) / 2)
    assert hook(overloaded, f"craneColor({row[3]})") == ACTIVITY_COLORS["moving_empty"]


def test_legend_explains_crane_colors(v1: Page) -> None:
    legend = v1.locator("#crane-legend").inner_text()
    for label in ("Moving empty", "Moving loaded", "Handling", "Idle"):
        assert label in legend


def test_figures_show_time_window_and_identification(v1: Page) -> None:
    move_to(v1, 10)
    assert figure(v1, "window") == "Warm-up"
    move_to(v1, 30)
    assert figure(v1, "window") == "Measurement window"
    assert figure(v1, "completed") == "1"
    assert figure(v1, "occupancy") == "1.000000"
    run = v1.locator("#run-identification").inner_text()
    assert "verification-v1" in run
    assert "verification-v3" in run
    assert "Seed: 1" in run


def test_figures_show_backlog_in_total_per_aisle_and_waiting(overloaded: Page) -> None:
    peak = hook(overloaded, "reportedPeak")
    move_to(overloaded, peak)
    summary = hook(overloaded, "summary()")
    backlog = summary["backlog"]
    assert figure(overloaded, "backlog") == str(backlog["total"])
    assert figure(overloaded, "waiting") == str(backlog["waiting_for_cell"])
    per_aisle = overloaded.locator("#figure-per-aisle").inner_text()
    for aisle, count in backlog["per_aisle"].items():
        assert f"Aisle {aisle}: {count}" in per_aisle


def test_overloaded_aisle_stands_out_at_the_peak(overloaded: Page) -> None:
    move_to(overloaded, hook(overloaded, "reportedPeak"))
    per_aisle = hook(overloaded, "summary()")["backlog"]["per_aisle"]
    assert per_aisle["1"] > 0
    assert per_aisle["1"] > max(count for aisle, count in per_aisle.items() if aisle != "1")


def test_end_of_run_figures_equal_the_report(overloaded: Page, overloaded_output: Path) -> None:
    move_to(overloaded, hook(overloaded, "duration_s"))
    report = (overloaded_output / "report.md").read_text("utf-8")
    assert f"Orders completed: {figure(overloaded, 'completed')}\n" in report
    assert f"Backlog at window end: {figure(overloaded, 'backlog')} orders\n" in report
    assert f"Occupancy at window end: {figure(overloaded, 'occupancy')}\n" in report
    assert f"Orders unfulfillable: {figure(overloaded, 'unfulfillable')}\n" in report


def test_go_to_highest_backlog(overloaded: Page, overloaded_output: Path) -> None:
    data = replay_data(overloaded_output)
    overloaded.locator("#speed").select_option("10")
    overloaded.locator("#play").click()
    overloaded.locator("#go-to-peak").click()
    assert hook(overloaded, "playing") is False
    assert hook(overloaded, "time_s") == data["reported"]["first_backlog_peak_s"]
    maximum = data["reported"]["backlog_orders"]["max_in_window"]
    assert maximum > 0
    assert figure(overloaded, "backlog") == str(maximum)
    assert figure(overloaded, "window") == "Measurement window"


def test_time_just_before_the_peak_has_a_lower_backlog(
    overloaded: Page, overloaded_output: Path
) -> None:
    data = replay_data(overloaded_output)
    peak = data["reported"]["first_backlog_peak_s"]
    assert peak > data["run"]["window"]["start_s"]
    move_to(overloaded, peak - 0.001)
    maximum = data["reported"]["backlog_orders"]["max_in_window"]
    assert hook(overloaded, "summary()")["backlog"]["total"] < maximum


def test_unfulfillable_count_is_shown_at_its_time(
    overloaded: Page, overloaded_output: Path
) -> None:
    data = replay_data(overloaded_output)
    move_to(overloaded, data["run"]["duration_s"])
    assert figure(overloaded, "unfulfillable") == str(
        data["reported"]["order_outcomes"]["unfulfillable"]
    )


def working_crane_pixels(page: Page) -> int:
    """Count the drawn pixels in the hues of a working crane, which nothing else uses."""
    return page.evaluate(
        """() => {
            const canvas = document.querySelector('#view canvas');
            const copy = document.createElement('canvas');
            copy.width = canvas.width;
            copy.height = canvas.height;
            window.highbayViewer.renderNow();
            const context = copy.getContext('2d');
            context.drawImage(canvas, 0, 0);
            const { data } = context.getImageData(0, 0, copy.width, copy.height);
            let count = 0;
            for (let i = 0; i < data.length; i += 4) {
                const [r, g, b] = [data[i], data[i + 1], data[i + 2]];
                const max = Math.max(r, g, b);
                const range = max - Math.min(r, g, b);
                if (range === 0 || range / max <= 0.5 || max <= 76) continue;
                let sector = (r - g) / range + 4;
                if (max === r) sector = ((g - b) / range + 6) % 6;
                else if (max === g) sector = (b - r) / range + 2;
                const hue = sector * 60;
                if ((hue >= 18 && hue <= 36) || (hue >= 205 && hue <= 285)) count += 1;
            }
            return count;
        }"""
    )


def test_default_view_shows_a_working_crane_among_stored_stock(
    page: Page, serve: Callable[[Path], str], overloaded_output: Path
) -> None:
    open_viewer(page, serve(overloaded_output / "replay.json"))
    counts = []
    for time_s in range(2490, 3567, 108):
        move_to(page, time_s)
        assert hook(page, "crane(1)")["activity"] != "idle"
        counts.append(working_crane_pixels(page))
    assert min(counts) >= 90, counts
