"""Shared test helpers: valid inputs, a local viewer server, and a headless browser with WebGL."""

import json
import threading
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml
from playwright.sync_api import Browser, Error, Page, sync_playwright

from highbay_sim.cli import main
from highbay_sim.viewer_server import ViewerServer, create_server

ROOT = Path(__file__).parents[1]
SAMPLES = ROOT / "samples"


def minimal_warehouse_dict() -> dict[str, Any]:
    """One aisle, one rack, 5 bays, 2 levels: the warehouse used for hand calculations."""
    return {
        "schema_version": 1,
        "name": "minimal",
        "layout": {
            "aisle_count": 1,
            "racks_per_aisle": 1,
            "bays_per_rack": 5,
            "levels_per_rack": 2,
            "cell": {"height_m": 3.0, "length_m": 4.0, "width_m": 1.5},
        },
        "crane": {
            "horizontal": {"speed_m_s": 2.0, "acceleration_m_s2": 1.0},
            "vertical": {"speed_m_s": 1.0, "acceleration_m_s2": 1.0},
            "pick_time_s": 10.0,
            "set_time_s": 10.0,
        },
        "transfer_points": {"default": {"left": ["inbound"], "right": ["outbound"]}},
        "storage_rule": "nearest_free",
        "initial_stock": [],
    }


def minimal_scenario_dict() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "name": "minimal-scenario",
        "seed": 1,
        "duration_s": 3600,
        "warmup_s": 0,
        "orders": [],
    }


def write_yaml(path: Path, content: dict[str, Any]) -> Path:
    path.write_text(yaml.safe_dump(content, sort_keys=False), encoding="utf-8", newline="\n")
    return path


BROWSER_ARGUMENTS = [
    "--use-angle=swiftshader",
    "--enable-unsafe-swiftshader",
    "--ignore-gpu-blocklist",
]


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if "viewer" in item.path.parts or item.path.name == "test_crane_positions.py":
            item.add_marker(pytest.mark.viewer)


@pytest.fixture(scope="session")
def browser() -> Iterator[Browser]:
    with sync_playwright() as playwright:
        try:
            instance = playwright.chromium.launch(args=BROWSER_ARGUMENTS)
        except Error as error:
            pytest.fail(
                f"Chromium is needed for viewer tests: run 'uv run playwright install chromium'. "
                f"{error}"
            )
        yield instance
        instance.close()


@pytest.fixture
def serve() -> Iterator[Callable[[Path], str]]:
    """Return a function that serves a replay file and returns the viewer's address."""
    servers: list[tuple[ViewerServer, threading.Thread]] = []

    def start(replay_path: Path) -> str:
        server = create_server(replay_path)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        servers.append((server, thread))
        return server.address

    yield start
    for server, thread in servers:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.fixture
def page(browser: Browser) -> Iterator[Page]:
    instance = browser.new_page(viewport={"width": 1280, "height": 800})
    yield instance
    instance.close()


@pytest.fixture
def write_run(tmp_path: Path) -> Callable[..., Path]:
    """Return a function that runs inputs with --replay and returns the output directory."""
    count = [0]

    def run(warehouse: Path, scenario: Path) -> Path:
        count[0] += 1
        output = tmp_path / f"run-{count[0]}"
        arguments = ["run", str(warehouse), str(scenario), "--output", str(output), "--replay"]
        assert main(arguments) == 0
        return output

    return run


class Modules:
    """Calls functions of the viewer's logic modules inside the browser page."""

    def __init__(self, page: Page, address: str) -> None:
        self.page = page
        page.goto(f"{address}style.css")

    def call(self, module: str, function: str, *arguments: Any) -> Any:
        return self.page.evaluate(
            "async ([module, name, args]) => (await import(module))[name](...args)",
            [f"/{module}", function, list(arguments)],
        )

    def run(self, script: str, *arguments: Any) -> Any:
        """Run an async function body with `imports(name)` and `args` available."""
        return self.page.evaluate(
            f"async (args) => {{ const imports = (name) => import('/' + name); {script} }}",
            list(arguments),
        )


@pytest.fixture
def modules(page: Page, serve: Callable[[Path], str], tmp_path: Path) -> Modules:
    placeholder = tmp_path / "placeholder.json"
    placeholder.write_text("{}", encoding="utf-8")
    return Modules(page, serve(placeholder))


def replay_data(output: Path) -> dict[str, Any]:
    return json.loads((output / "replay.json").read_text(encoding="utf-8"))
