"""The command-line interface, as in contracts/cli.md."""

import argparse
import contextlib
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from highbay_sim import __version__
from highbay_sim.compare import ComparisonError, compare_results, load_result
from highbay_sim.config import (
    InputError,
    Loaded,
    Scenario,
    WarehouseDefinition,
    load_inputs,
    load_warehouse,
)
from highbay_sim.controller import (
    Controller,
    ControllerLoadError,
    ControllerStopped,
    load_controller,
)
from highbay_sim.engine import simulate
from highbay_sim.metrics import calculate_metrics
from highbay_sim.orders import order_source_for
from highbay_sim.outputs import (
    REPLAY_FILE,
    SIGNAL_FILE,
    Execution,
    RunInfo,
    existing_outputs,
    write_outputs,
)
from highbay_sim.plc.controller import PlcController, PlcRefused
from highbay_sim.plc.interface import PlcInterface
from highbay_sim.plc.link import LinkError, PlcConnection, open_link
from highbay_sim.plc.measure import measure
from highbay_sim.plc.source import SOURCE_FILES, generate_sources
from highbay_sim.replay import build_replay, write_replay
from highbay_sim.signal_record import SignalRecorder
from highbay_sim.signals import SIGNAL_LIST_VERSION, Fault
from highbay_sim.stepped import (
    DEFAULT_CYCLE_MS,
    MAX_CYCLE_MS,
    MIN_CYCLE_MS,
    new_signals,
    simulate_stepped,
)

EXIT_SUCCESS = 0
EXIT_FAILURE = 1
EXIT_INVALID_INPUT = 2


def main(arguments: Sequence[str] | None = None) -> int:
    parser = _parser()
    parsed = parser.parse_args(arguments)
    if parsed.command == "run":
        _check_run_options(parser, parsed)
    try:
        if parsed.command == "validate":
            return _validate(parsed.warehouse, parsed.scenario)
        if parsed.command == "view":
            return _view(parsed.path, parsed.port, not parsed.no_browser)
        if parsed.command == "compare":
            return _compare(parsed.first, parsed.second)
        if parsed.command == "plc-measure":
            connection = _plc_connection(parsed.plc_host, parsed.plc_tls_ca)
            assert connection is not None
            return _plc_measure(
                parsed.warehouse, connection, parsed.cycle_ms or DEFAULT_CYCLE_MS, parsed.seconds
            )
        if parsed.command == "plc-source":
            return _plc_source(
                parsed.warehouse,
                parsed.output,
                parsed.overwrite,
                parsed.cycle_ms or DEFAULT_CYCLE_MS,
            )
        return _run(
            parsed.warehouse,
            parsed.scenario,
            parsed.output,
            parsed.overwrite,
            parsed.replay,
            (parsed.cycle_ms or DEFAULT_CYCLE_MS) if parsed.time_stepped else None,
            parsed.controller,
            parsed.record_signals,
            _plc_connection(parsed.plc_host, parsed.plc_tls_ca),
        )
    except (ControllerLoadError, PlcRefused, LinkError) as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_INVALID_INPUT
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
    run.add_argument("--time-stepped", action="store_true", help="use the plant model in cycles")
    run.add_argument(
        "--cycle-ms", type=_cycle_ms, help=f"cycle time in ms (default: {DEFAULT_CYCLE_MS})"
    )
    run.add_argument("--controller", help="controller to use, as FILE.py:CLASS (runs that file)")
    run.add_argument("--record-signals", action="store_true", help="also write signals.csv")
    _add_plc_options(run)

    compare = commands.add_parser("compare", help="show how the results of two runs deviate")
    compare.add_argument("first", type=Path, help="a result.json file, or a directory with one")
    compare.add_argument("second", type=Path, help="a result.json file, or a directory with one")

    view = commands.add_parser("view", help="open a run's replay in the local 3D viewer")
    view.add_argument("path", type=Path, help="a replay.json file, or a directory containing one")
    view.add_argument("--port", type=int, default=0, help="port to use (default: any free port)")
    view.add_argument("--no-browser", action="store_true", help="do not open a web browser")

    source = commands.add_parser("plc-source", help="generate source files for TIA Portal")
    source.add_argument("warehouse", type=Path)
    source.add_argument("--output", type=Path, required=True, help="directory for the files")
    source.add_argument("--overwrite", action="store_true", help="replace existing files")
    source.add_argument(
        "--cycle-ms", type=_cycle_ms, help=f"cycle time in ms (default: {DEFAULT_CYCLE_MS})"
    )

    plc_measure = commands.add_parser("plc-measure", help="measure the exchange with a PLC")
    plc_measure.add_argument("warehouse", type=Path)
    plc_measure.add_argument("--plc-host", required=True, help="address of a simulated PLC")
    plc_measure.add_argument("--plc-tls-ca", help="certificate file to verify the PLC with")
    plc_measure.add_argument(
        "--cycle-ms", type=_cycle_ms, help=f"cycle time in ms (default: {DEFAULT_CYCLE_MS})"
    )
    plc_measure.add_argument(
        "--seconds", type=float, default=60.0, help="how long to measure (default: 60)"
    )
    return parser


def _add_plc_options(command: argparse.ArgumentParser) -> None:
    command.add_argument("--plc-host", help="address of a simulated PLC, as the controller")
    command.add_argument("--plc-tls-ca", help="certificate file to verify the PLC with")


def _plc_connection(host: str | None, tls_ca: str | None) -> PlcConnection | None:
    if host is None:
        return None
    return PlcConnection(host, tls_ca, os.environ.get("HIGHBAY_PLC_PASSWORD") or None)


def _cycle_ms(value: str) -> int:
    allowed = f"a whole number from {MIN_CYCLE_MS} to {MAX_CYCLE_MS}"
    try:
        cycle_ms = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value} is not {allowed}") from None
    if not MIN_CYCLE_MS <= cycle_ms <= MAX_CYCLE_MS:
        raise argparse.ArgumentTypeError(f"{value} is not {allowed}")
    return cycle_ms


def _check_run_options(parser: argparse.ArgumentParser, parsed: argparse.Namespace) -> None:
    if parsed.plc_tls_ca is not None and parsed.plc_host is None:
        parser.error("--plc-tls-ca needs --plc-host")
    if parsed.plc_host is not None and parsed.controller is not None:
        parser.error("--plc-host cannot be used with --controller")
    if parsed.time_stepped:
        return
    for given, option in (
        (parsed.cycle_ms is not None, "--cycle-ms"),
        (parsed.controller is not None, "--controller"),
        (parsed.record_signals, "--record-signals"),
        (parsed.plc_host is not None, "--plc-host"),
    ):
        if given:
            parser.error(f"{option} needs --time-stepped")


def _validate(warehouse_path: Path, scenario_path: Path) -> int:
    warehouse, _ = load_inputs(warehouse_path, scenario_path)
    layout = warehouse.model.layout
    print(f"Inputs are valid: {layout.aisle_count} aisles, {layout.cell_count} cells")
    return EXIT_SUCCESS


def _run(
    warehouse_path: Path,
    scenario_path: Path,
    output: Path,
    overwrite: bool,
    replay: bool,
    cycle_ms: int | None,
    controller_specification: str | None,
    record_signals: bool,
    plc_connection: PlcConnection | None,
) -> int:
    warehouse, scenario = load_inputs(warehouse_path, scenario_path)
    controller: Controller | None = None
    controller_name, controller_sha256 = "built-in", None
    if controller_specification is not None:
        controller, controller_name, controller_sha256 = load_controller(controller_specification)
    conflicts = existing_outputs(output)
    if conflicts and not overwrite:
        names = ", ".join(str(path) for path in conflicts)
        print(f"error: output files exist, use --overwrite to replace: {names}", file=sys.stderr)
        return EXIT_FAILURE
    if plc_connection is None:
        return _execute(
            warehouse,
            scenario,
            output,
            replay,
            cycle_ms,
            controller,
            controller_name,
            controller_sha256,
            record_signals,
            None,
        )
    assert cycle_ms is not None
    plc = _start_plc(plc_connection, warehouse.model, cycle_ms)
    try:
        return _execute(
            warehouse, scenario, output, replay, cycle_ms, plc, "plc", None, record_signals, plc
        )
    finally:
        plc.close()


def _start_plc(
    connection: PlcConnection, warehouse: WarehouseDefinition, cycle_ms: int
) -> PlcController:
    interface = PlcInterface.for_warehouse(warehouse)
    plc = PlcController(open_link(connection), interface, cycle_ms)
    plc.prepare()
    print(f"Connected to {plc.device}. A run takes as long in real time as it simulates.")
    return plc


def _execute(
    warehouse: Loaded[WarehouseDefinition],
    scenario: Loaded[Scenario],
    output: Path,
    replay: bool,
    cycle_ms: int | None,
    controller: Controller | None,
    controller_name: str,
    controller_sha256: str | None,
    record_signals: bool,
    plc: PlcController | None,
) -> int:
    execution = None
    stop = None
    warmup_s = scenario.model.warmup_s
    duration_s = scenario.model.duration_s
    faults: tuple[Fault, ...] = ()
    signal_path = output / SIGNAL_FILE
    # A signal record from an earlier run must never be read next to these results.
    signal_path.unlink(missing_ok=True)
    if cycle_ms is None:
        record = simulate(
            warehouse.model,
            order_source_for(scenario.model),
            scenario.model.seed,
            scenario.model.duration_s,
        )
    else:
        order_source = order_source_for(scenario.model)
        model, seed, duration_s = warehouse.model, scenario.model.seed, scenario.model.duration_s
        if record_signals:
            output.mkdir(parents=True, exist_ok=True)
            signals = new_signals(model)
            try:
                with SignalRecorder(signal_path, signals) as recorder:
                    stepped = simulate_stepped(
                        model,
                        order_source,
                        seed,
                        duration_s,
                        cycle_ms,
                        controller,
                        recorder.record,
                        signals,
                    )
            except BaseException:
                signal_path.unlink(missing_ok=True)
                raise
        else:
            stepped = simulate_stepped(model, order_source, seed, duration_s, cycle_ms, controller)
        record, faults, stop = stepped.record, stepped.faults, stepped.stop
        plc_section = None if plc is None else plc.stats().report()
        if stop is not None:
            duration_s = record.duration_s
            if warmup_s >= duration_s:
                warmup_s = 0.0
                if plc_section is not None:
                    plc_section["warmup_skipped"] = True
        execution = Execution(
            cycle_ms, controller_name, controller_sha256, SIGNAL_LIST_VERSION, plc_section
        )
    metrics = calculate_metrics(record, warmup_s)
    info = RunInfo(
        software_version=__version__,
        seed=scenario.model.seed,
        warehouse_name=warehouse.model.name,
        warehouse_sha256=warehouse.sha256,
        scenario_name=scenario.model.name,
        scenario_sha256=scenario.sha256,
        duration_s=duration_s,
        execution=execution,
    )
    # A replay file from an earlier run must never be viewable next to these results.
    (output / REPLAY_FILE).unlink(missing_ok=True)
    write_outputs(output, info, metrics, record.orders, faults)
    if replay:
        write_replay(output / REPLAY_FILE, build_replay(record, warehouse.model, info, metrics))
    print(f"Results written to {output}")
    print(f"Total throughput: {metrics.throughput_total:.3f} orders/hour")
    if stop is not None:
        print(
            f"error: the run stopped in cycle {stop.cycle} ({stop.reason}): {stop.message}",
            file=sys.stderr,
        )
        return EXIT_FAILURE
    return EXIT_SUCCESS


def _plc_source(warehouse_path: Path, output: Path, overwrite: bool, cycle_ms: int) -> int:
    interface = PlcInterface.for_warehouse(load_warehouse(warehouse_path).model)
    conflicts = [output / name for name in SOURCE_FILES if (output / name).exists()]
    if conflicts and not overwrite:
        names = ", ".join(str(path) for path in conflicts)
        print(f"error: files exist, use --overwrite to replace: {names}", file=sys.stderr)
        return EXIT_FAILURE
    output.mkdir(parents=True, exist_ok=True)
    for name, text in generate_sources(interface, cycle_ms).items():
        (output / name).write_text(text, encoding="utf-8", newline="\n")
    print(f"Source files written to {output}")
    return EXIT_SUCCESS


def _plc_measure(
    warehouse_path: Path, connection: PlcConnection, cycle_ms: int, seconds: float
) -> int:
    interface = PlcInterface.for_warehouse(load_warehouse(warehouse_path).model)
    plc = PlcController(open_link(connection), interface, cycle_ms)
    try:
        print(measure(plc, interface, cycle_ms, seconds).text())
    except ControllerStopped as stopped:
        print(f"error: the measurement stopped ({stopped.reason}): {stopped}", file=sys.stderr)
        return EXIT_FAILURE
    finally:
        plc.close()
    return EXIT_SUCCESS


def _compare(first: Path, second: Path) -> int:
    try:
        print(compare_results(load_result(first), load_result(second)))
    except ComparisonError as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_INVALID_INPUT
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
