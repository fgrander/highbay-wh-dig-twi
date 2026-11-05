"""plc-measure: how fast signals can be exchanged, with no plant and no jobs.

The positions change in each cycle, as for moving cranes, so that each exchange holds a write as
well as a read. No job is written, so the PLC program does nothing but its scan.
"""

import math
from dataclasses import dataclass

from highbay_sim.plc.controller import PlcController
from highbay_sim.plc.interface import PlcInterface
from highbay_sim.signals import CraneSignals

_POSITION_STEP_M = 0.001


@dataclass(frozen=True)
class Measurement:
    device: str
    crane_count: int
    cycle_ms: int
    cycles: int
    overrun_cycles: int
    median_ms: float
    p99_ms: float
    slowest_ms: float

    def text(self) -> str:
        return (
            f"Device: {self.device}\n"
            f"Cranes: {self.crane_count}\n"
            f"Exchange time: median {self.median_ms:.2f} ms, "
            f"99th percentile {self.p99_ms:.2f} ms, slowest {self.slowest_ms:.2f} ms\n"
            f"Overruns: {self.overrun_cycles} of {self.cycles} cycles at {self.cycle_ms} ms\n"
            "These figures hold only for this connection, with no plant running."
        )


def percentile(ordered: list[float], percent: int) -> float:
    """The nearest-rank percentile of values in ascending order."""
    return ordered[max(math.ceil(percent * len(ordered) / 100) - 1, 0)]


def measure(
    controller: PlcController, interface: PlcInterface, cycle_ms: int, seconds: float
) -> Measurement:
    """Carry out the start of a run, then exchange for the given time."""
    controller.prepare()
    signals = {aisle: CraneSignals() for aisle in interface.aisles}
    times: list[float] = []
    for cycle in range(1, max(round(seconds * 1000 / cycle_ms), 1) + 1):
        for crane in signals.values():
            crane.horizontal_actual_m = crane.vertical_actual_m = cycle * _POSITION_STEP_M
        controller.scan(signals)
        times.append(controller.last_exchange_ms)
    ordered = sorted(times)
    stats = controller.stats()
    return Measurement(
        device=stats.device,
        crane_count=interface.crane_count,
        cycle_ms=cycle_ms,
        cycles=stats.cycles,
        overrun_cycles=stats.overrun_cycles,
        median_ms=percentile(ordered, 50),
        p99_ms=percentile(ordered, 99),
        slowest_ms=ordered[-1],
    )
