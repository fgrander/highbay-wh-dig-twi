"""The viewer through its interface and read-only test hook."""

import copy
import hashlib
import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from playwright.sync_api import Page

from conftest import SAMPLES, minimal_scenario_dict, minimal_warehouse_dict, replay_data, write_yaml

VIEWER_DIRECTORY = Path(__file__).parents[2] / "src" / "highbay_sim" / "viewer"
SMALL = (SAMPLES / "small-warehouse.yaml", SAMPLES / "daily-scenario.yaml")


def open_viewer(page: Page, address: str) -> None:
    page.goto(address)
    page.wait_for_function("window.highbayViewer !== undefined")
    page.evaluate("window.highbayViewer.ready")


def hook(page: Page, expression: str) -> Any:
    return page.evaluate(f"window.highbayViewer.{expression}")


@pytest.fixture
def small_run(write_run: Callable[..., Path]) -> Path:
    return write_run(*SMALL)


@pytest.fixture
def opened(page: Page, serve: Callable[[Path], str], small_run: Path) -> Page:
    open_viewer(page, serve(small_run / "replay.json"))
    return page


def test_scene_matches_the_warehouse_definition(opened: Page) -> None:
    info = hook(opened, "sceneInfo()")
    assert info["aisles"] == 4
    assert info["racks"] == 8
    assert info["cells"] == 3200
    assert info["cranes"] == 4
    assert info["transfer_points"] == 8
    assert info["load_units"] == 160
    assert hook(opened, "lastError") is None


def test_initial_values_and_time_label(opened: Page) -> None:
    assert hook(opened, "time_s") == 0.0
    assert hook(opened, "playing") is False
    assert hook(opened, "speed") == 60
    assert "0" in opened.locator("#time-label").inner_text()


def test_play_advances_time_and_moves_a_crane(opened: Page) -> None:
    opened.locator("#speed").select_option("3600")
    assert hook(opened, "speed") == 3600
    opened.locator("#play").click()
    assert hook(opened, "playing") is True
    opened.wait_for_function(
        "() => [1, 2, 3, 4].some((aisle) => window.highbayViewer.crane(aisle).activity !== 'idle')"
    )
    assert hook(opened, "time_s") > 0.0


def test_pause_stops_time(opened: Page) -> None:
    opened.locator("#speed").select_option("3600")
    opened.locator("#play").click()
    opened.wait_for_function("window.highbayViewer.time_s > 0")
    opened.locator("#play").click()
    paused = hook(opened, "time_s")
    assert hook(opened, "playing") is False
    opened.wait_for_timeout(200)
    assert hook(opened, "time_s") == paused


def test_slider_moves_to_a_time_and_the_scene_follows(opened: Page) -> None:
    opened.locator("#time-slider").fill("40000")
    assert hook(opened, "time_s") == pytest.approx(40000.0)
    info = hook(opened, "sceneInfo()")
    summary = hook(opened, "summary()")
    assert info["load_units"] == summary["occupied_cells"]
    assert info["load_units"] == len(hook(opened, "storedLoadUnits()"))
    opened.locator("#time-slider").fill("0")
    assert hook(opened, "sceneInfo()")["load_units"] == 160


def test_restart_goes_to_zero_and_pauses(opened: Page) -> None:
    opened.locator("#time-slider").fill("40000")
    opened.locator("#speed").select_option("10")
    opened.locator("#play").click()
    opened.locator("#restart").click()
    assert hook(opened, "time_s") == 0.0
    assert hook(opened, "playing") is False


def test_playback_stops_at_the_end_and_shows_the_final_state(opened: Page) -> None:
    duration = hook(opened, "duration_s")
    opened.locator("#time-slider").fill(str(duration - 10))
    opened.locator("#speed").select_option("3600")
    opened.locator("#play").click()
    opened.wait_for_function("window.highbayViewer.playing === false")
    assert hook(opened, "time_s") == duration


def test_scene_draws_pixels(opened: Page) -> None:
    opened.wait_for_timeout(200)
    drawn = opened.evaluate(
        """() => {
            const canvas = document.querySelector('#view canvas');
            const copy = document.createElement('canvas');
            copy.width = canvas.width;
            copy.height = canvas.height;
            window.highbayViewer.renderNow();
            const context = copy.getContext('2d');
            context.drawImage(canvas, 0, 0);
            const { data } = context.getImageData(0, 0, copy.width, copy.height);
            const colors = new Set();
            for (let i = 0; i < data.length; i += 4 * 97) {
                colors.add(`${data[i]},${data[i + 1]},${data[i + 2]}`);
            }
            return colors.size;
        }"""
    )
    assert drawn > 2


def test_articles_have_distinct_colors_and_a_legend(opened: Page) -> None:
    legend = opened.locator("#legend")
    assert "oak-panel-18mm" in legend.inner_text()
    assert "paper-a4-80g" in legend.inner_text()
    colors = hook(opened, "sceneInfo()")["article_colors"]
    assert len(set(colors)) == 2


def test_every_request_goes_to_the_local_server(
    page: Page, serve: Callable[[Path], str], small_run: Path
) -> None:
    address = serve(small_run / "replay.json")
    requests: list[str] = []
    failures: list[str] = []
    page.on("request", lambda request: requests.append(request.url))
    page.on("requestfailed", lambda request: failures.append(request.url))
    page.on(
        "response",
        lambda response: failures.append(response.url) if response.status >= 400 else None,
    )
    open_viewer(page, address)
    assert requests
    outside = [url for url in requests if not url.startswith(address)]
    assert outside == []
    assert [url for url in failures if not url.endswith("favicon.ico")] == []


def test_viewing_changes_no_run_file(
    page: Page, serve: Callable[[Path], str], small_run: Path
) -> None:
    def hashes() -> dict[str, str]:
        return {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(small_run.iterdir())
        }

    before = hashes()
    open_viewer(page, serve(small_run / "replay.json"))
    page.locator("#play").click()
    page.locator("#time-slider").fill("1000")
    page.locator("#restart").click()
    assert hashes() == before


def damaged(path: Path, change: Callable[[dict[str, Any]], None]) -> None:
    content = json.loads(path.read_text(encoding="utf-8"))
    change(content)
    path.write_text(json.dumps(content), encoding="utf-8")


@pytest.mark.parametrize(
    "change",
    [
        lambda c: c.update(format_version=999),
        lambda c: c.pop("events"),
        lambda c: c.update(orders="wrong"),
    ],
    ids=["version", "missing-events", "wrong-orders"],
)
def test_damaged_file_shows_a_message_and_no_warehouse(
    page: Page,
    serve: Callable[[Path], str],
    small_run: Path,
    change: Callable[[dict[str, Any]], None],
) -> None:
    damaged(small_run / "replay.json", change)
    open_viewer(page, serve(small_run / "replay.json"))
    assert page.locator("#error").is_visible()
    assert page.locator("#error").inner_text()
    assert page.locator("#view canvas").count() == 0
    assert hook(page, "lastError")


def test_truncated_file_shows_a_message_and_no_warehouse(
    page: Page, serve: Callable[[Path], str], small_run: Path
) -> None:
    path = small_run / "replay.json"
    path.write_bytes(path.read_bytes()[:1000])
    open_viewer(page, serve(path))
    assert page.locator("#error").is_visible()
    assert page.locator("#view canvas").count() == 0


def test_missing_webgl_shows_a_message(
    page: Page, serve: Callable[[Path], str], small_run: Path
) -> None:
    page.add_init_script(
        "const original = HTMLCanvasElement.prototype.getContext;"
        "HTMLCanvasElement.prototype.getContext = function (kind, ...rest) {"
        "  return kind.startsWith('webgl') ? null : original.call(this, kind, ...rest);"
        "};"
    )
    open_viewer(page, serve(small_run / "replay.json"))
    assert "WebGL" in page.locator("#error").inner_text()
    assert page.locator("#view canvas").count() == 0


def test_hook_is_read_only(opened: Page) -> None:
    assert opened.evaluate(
        "() => { try { window.highbayViewer.time_s = 5; } catch { /* strict mode */ }"
        " return window.highbayViewer.time_s === 0; }"
    )
    assert opened.evaluate("Object.isFrozen(window.highbayViewer)")


def test_whole_warehouse_is_in_the_initial_view_at_any_size(
    page: Page,
    serve: Callable[[Path], str],
    write_run: Callable[..., Path],
    tmp_path: Path,
) -> None:
    small = minimal_warehouse_dict()
    large = copy.deepcopy(small)
    large["layout"].update(aisle_count=20, racks_per_aisle=2, bays_per_rack=50, levels_per_rack=50)
    scenario = write_yaml(tmp_path / "s.yaml", minimal_scenario_dict())
    for index, warehouse in enumerate((small, large)):
        output = write_run(write_yaml(tmp_path / f"w{index}.yaml", warehouse), scenario)
        open_viewer(page, serve(output / "replay.json"))
        assert hook(page, "boundsInView()") is True


def test_three_objects_are_created_only_in_appearance_module() -> None:
    pattern = re.compile(
        r"new\s+THREE\.\w*(Geometry|Material|Mesh|LineSegments|Line|Points|Sprite)\b"
    )
    for path in VIEWER_DIRECTORY.glob("*.js"):
        matches = pattern.findall(path.read_text(encoding="utf-8"))
        if path.name == "appearance.js":
            assert matches, "appearance.js is expected to create the objects"
        else:
            assert matches == [], f"{path.name} creates three.js objects"


def test_benchmark_mode_reports_numbers(
    page: Page, serve: Callable[[Path], str], small_run: Path
) -> None:
    # A shorter measurement than the normal 20 s. No frame rate is required in software rendering.
    page.goto(f"{serve(small_run / 'replay.json')}?benchmark=1&seconds=2")
    page.wait_for_function("window.highbayViewer !== undefined")
    page.evaluate("window.highbayViewer.ready")
    assert hook(page, "playing") is True
    assert hook(page, "speed") == 600
    page.wait_for_function("window.highbayViewer.benchmark !== null", timeout=30_000)
    result = hook(page, "benchmark")
    assert result["frames"] > 0
    assert result["average_fps"] > 0
    assert result["slowest_frame_ms"] > 0
    assert "frames per second" in page.locator("#benchmark").inner_text()


def test_no_benchmark_without_asking(opened: Page) -> None:
    assert hook(opened, "benchmark") is None
    assert opened.locator("#benchmark").is_hidden()


def test_replay_data_reaches_the_viewer_unchanged(opened: Page, small_run: Path) -> None:
    assert hook(opened, "duration_s") == replay_data(small_run)["run"]["duration_s"]
