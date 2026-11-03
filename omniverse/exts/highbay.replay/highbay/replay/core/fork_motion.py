"""Where a crane's forks and load are shown during a handling step, for display only.

This depends only on the step, the time, and the layout, so any way of reaching a time shows the
same. The division of a step is not recorded, and nothing else depends on it.
"""

from dataclasses import dataclass

from .layout import Layout
from .state_source import HandlingStep, Location

EXTENDED_AT_SHARE = 0.4
RETURNING_AT_SHARE = 0.6


@dataclass(frozen=True, slots=True)
class ForkPose:
    extension_m: float
    load_offset_m: float
    load_on_crane: bool
    hidden_cell: Location | None


REST = ForkPose(0.0, 0.0, False, None)


def fork_pose(step: HandlingStep | None, time_s: float, layout: Layout) -> ForkPose:
    """Returns the forks' and load's distances from the crane's center, signed towards a rack."""
    if step is None or step.location is None or step.end_s <= step.start_s:
        return REST
    aisle, rack, _bay, _level = step.location
    reach = layout.rack_z(aisle, rack) - layout.aisle_center_z(aisle)
    share = min(max((time_s - step.start_s) / (step.end_s - step.start_s), 0.0), 1.0)
    if share < EXTENDED_AT_SHARE:
        extended = share / EXTENDED_AT_SHARE
    elif share <= RETURNING_AT_SHARE:
        extended = 1.0
    else:
        extended = (1.0 - share) / (1.0 - RETURNING_AT_SHARE)
    if step.kind == "pick":
        # It waits at the cell until the forks take it back. The recording moves it at the end.
        moved = 1.0 if share <= RETURNING_AT_SHARE else extended
        return ForkPose(reach * extended, reach * moved, True, step.location)
    # It goes out with the forks, and waits at the cell for the recording to store it.
    moved = extended if share < EXTENDED_AT_SHARE else 1.0
    return ForkPose(reach * extended, reach * moved, True, None)
