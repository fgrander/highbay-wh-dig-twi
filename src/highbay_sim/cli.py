"""The command-line interface, as in contracts/cli.md."""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from highbay_sim import __version__
from highbay_sim.config import InputError, load_inputs
from highbay_sim.engine import simulate
from highbay_sim.metrics import calculate_metrics
from highbay_sim.orders import order_source_for
from highbay_sim.outputs import RunInfo, existing_outputs, write_outputs

EXIT_SUCCESS = 0
EXIT_FAILURE = 1
EXIT_INVALID_INPUT = 2


def main(arguments: Sequence[str] | None = None) -> int:
    parsed = _parser().parse_args(arguments)
    try:
        if parsed.command == "validate":
            return _validate(parsed.warehouse, parsed.scenario)
        return _run(parsed.warehouse, parsed.scenario, parsed.output, parsed.overwrite)
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
    return parser


def _validate(warehouse_path: Path, scenario_path: Path) -> int:
    warehouse, _ = load_inputs(warehouse_path, scenario_path)
    layout = warehouse.model.layout
    print(f"Inputs are valid: {layout.aisle_count} aisles, {layout.cell_count} cells")
    return EXIT_SUCCESS


def _run(warehouse_path: Path, scenario_path: Path, output: Path, overwrite: bool) -> int:
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
    write_outputs(output, info, metrics, record.orders)
    print(f"Results written to {output}")
    print(f"Total throughput: {metrics.throughput_total:.3f} orders/hour")
    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main())
