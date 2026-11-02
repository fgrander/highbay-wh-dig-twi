"""The command-line interface, as in contracts/cli.md."""

import argparse
import contextlib
import sys
from collections.abc import Sequence
from pathlib import Path

from highbay_sim import __version__
from highbay_sim.config import InputError, load_inputs
from highbay_sim.engine import simulate
from highbay_sim.metrics import calculate_metrics
from highbay_sim.orders import order_source_for
from highbay_sim.outputs import REPLAY_FILE, RunInfo, existing_outputs, write_outputs
from highbay_sim.replay import build_replay, write_replay

EXIT_SUCCESS = 0
EXIT_FAILURE = 1
EXIT_INVALID_INPUT = 2


def main(arguments: Sequence[str] | None = None) -> int:
    parsed = _parser().parse_args(arguments)
    try:
        if parsed.command == "validate":
            return _validate(parsed.warehouse, parsed.scenario)
        if parsed.command == "view":
            return _view(parsed.path, parsed.port, not parsed.no_browser)
        return _run(
            parsed.warehouse, parsed.scenario, parsed.output, parsed.overwrite, parsed.replay
        )
    except InputError as error:
        for problem in error.problems:
            print(problem, file=sys.stderr)
        return EXIT_INVALID_INPUT
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_FAILURE


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="highbay-sim", description="Headless throughput simulation of a high-bay warehouse."
    )
    parser.add_argument("--version", action="version", version=f"highbay-sim {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate", help="check input files without simulating")
    validate.add_argument("warehouse", type=Path)
    validate.add_argument("scenario", type=Path)

    run = commands.add_parser("run", help="validate the inputs, simulate, and write results")
    run.add_argument("warehouse", type=Path)
    run.add_argument("scenario", type=Path)
    run.add_argument("--output", type=Path, required=True, help="directory for the output files")
    run.add_argument("--overwrite", action="store_true", help="replace existing output files")
    run.add_argument("--replay", action="store_true", help="also write replay.json for the viewer")

    view = commands.add_parser("view", help="open a run's replay in the local 3D viewer")
    view.add_argument("path", type=Path, help="a replay.json file, or a directory containing one")
    view.add_argument("--port", type=int, default=0, help="port to use (default: any free port)")
    view.add_argument("--no-browser", action="store_true", help="do not open a web browser")
    return parser


def _validate(warehouse_path: Path, scenario_path: Path) -> int:
    warehouse, _ = load_inputs(warehouse_path, scenario_path)
    layout = warehouse.model.layout
    print(f"Inputs are valid: {layout.aisle_count} aisles, {layout.cell_count} cells")
    return EXIT_SUCCESS


def _run(
    warehouse_path: Path, scenario_path: Path, output: Path, overwrite: bool, replay: bool
) -> int:
    warehouse, scenario = load_inputs(warehouse_path, scenario_path)
    conflicts = existing_outputs(output)
    if conflicts and not overwrite:
        names = ", ".join(str(path) for path in conflicts)
        print(f"error: output files exist, use --overwrite to replace: {names}", file=sys.stderr)
        return EXIT_FAILURE

    record = simulate(
        warehouse.model,
        order_source_for(scenario.model),
        scenario.model.seed,
        scenario.model.duration_s,
    )
    metrics = calculate_metrics(record, scenario.model.warmup_s)
    info = RunInfo(
        software_version=__version__,
        seed=scenario.model.seed,
        warehouse_name=warehouse.model.name,
        warehouse_sha256=warehouse.sha256,
        scenario_name=scenario.model.name,
        scenario_sha256=scenario.sha256,
        duration_s=scenario.model.duration_s,
    )
    # A replay file from an earlier run must never be viewable next to these results.
    (output / REPLAY_FILE).unlink(missing_ok=True)
    write_outputs(output, info, metrics, record.orders)
    if replay:
        write_replay(output / REPLAY_FILE, build_replay(record, warehouse.model, info, metrics))
    print(f"Results written to {output}")
    print(f"Total throughput: {metrics.throughput_total:.3f} orders/hour")
    return EXIT_SUCCESS


def _view(path: Path, port: int, open_browser: bool) -> int:
    # Imported here, so that simulation runs load no server or browser code.
    import webbrowser

    from highbay_sim.viewer_server import create_server

    replay_path = path / REPLAY_FILE if path.is_dir() else path
    if not replay_path.is_file():
        print(f"error: no replay file found at {replay_path}", file=sys.stderr)
        return EXIT_INVALID_INPUT
    try:
        server = create_server(replay_path, port)
    except OSError as error:
        print(f"error: cannot use port {port}: {error}", file=sys.stderr)
        return EXIT_FAILURE

    with server:
        print(f"Viewer running at {server.address}")
        print("Press Ctrl+C to stop.", flush=True)
        if open_browser:
            webbrowser.open(server.address)
        with contextlib.suppress(KeyboardInterrupt):
            server.serve_forever()
    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main())
