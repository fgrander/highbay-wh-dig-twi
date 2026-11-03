"""The sizes of a two-column crane, for both its model and selection.

All values are placeholders for a general crane, not a manufacturer's model. Those that do not
follow from the warehouse are the constants below. Heights are above the floor of a cell.
"""

from dataclasses import dataclass

from .layout import RACK_MEMBER_THICKNESS_M, Box, Layout, Vector

COLUMN_WIDTH_M = 0.34
COLUMN_DEPTH_M = 0.5
COLUMN_CLEARANCE_M = 0.25
RAIL_WIDTH_M = 0.06
RAIL_SPAN_M = 0.38
BOGIE_LENGTH_M = 1.1
BOGIE_HEIGHT_M = 0.42
BOGIE_DEPTH_M = 0.7
BOGIE_STRIPE_HEIGHT_M = 0.03
WHEEL_RADIUS_M = 0.2
WHEEL_WIDTH_M = 0.12
FLOOR_TIE_HEIGHT_M = 0.04
FLOOR_TIE_DEPTH_M = 0.3
TOP_BEAM_HEIGHT_M = 0.3
TOP_ROLLER_HEIGHT_M = 0.1
TOP_ROLLER_DEPTH_M = 0.72
CABINET_WIDTH_M = 0.4
CABINET_HEIGHT_M = 1.1
CABINET_DEPTH_M = 0.5
LADDER_WIDTH_M = 0.42
LADDER_MEMBER_M = 0.04
END_FRAME_M = 0.12
END_FRAME_DEPTH_M = 0.6
END_FRAME_GAP_M = 0.06
ROLLER_WIDTH_M = 0.06
MINIMUM_END_FRAME_HEIGHT_M = 0.6
END_FRAME_HEIGHT_SHARE = 0.6
PLATE_DEPTH_M = 0.4
MINIMUM_PLATE_THICKNESS_M = 0.002
FORK_GAP_ABOVE_BEAM_M = 0.005
MINIMUM_FORK_THICKNESS_M = 0.02
STAGE_WIDTH_M = 0.07
FORK_LENGTH_SHARE = 0.85
TINE_SPACING_SHARE = 0.075
# In a long cell, each section stands where every part of a split stack covers it.
SECTION_FROM_END_M = 0.85

BOGIE_TOP_M = WHEEL_RADIUS_M + BOGIE_HEIGHT_M
TRAVEL_GEAR_HEIGHT_M = BOGIE_TOP_M + BOGIE_STRIPE_HEIGHT_M


@dataclass(frozen=True, slots=True)
class CraneDimensions:
    height: float
    column_x: float
    section_x: float
    reach: float
    fork_top: float
    fork_bottom: float
    plate_bottom: float
    fork_length: float
    tine_spacing: float
    frame_x: float
    frame_height: float
    cell_height: float

    @property
    def ladder_height(self) -> float:
        return self.height - TOP_BEAM_HEIGHT_M - BOGIE_TOP_M

    @property
    def ladder_x(self) -> float:
        return -self.column_x - COLUMN_WIDTH_M / 2 - LADDER_MEMBER_M

    @property
    def cabinet_x(self) -> float:
        return -self.column_x - BOGIE_LENGTH_M + COLUMN_WIDTH_M + CABINET_WIDTH_M / 2

    def bogie_x(self, side: float) -> float:
        """Returns the center of a bogie, which sticks out on a column's outer side."""
        return side * (self.column_x + (BOGIE_LENGTH_M - COLUMN_WIDTH_M) / 2)

    def rail_x(self, side: float) -> float:
        """Returns the center of a column's rail, on its side towards the load."""
        return side * (self.column_x - COLUMN_WIDTH_M / 2 - RAIL_WIDTH_M / 2)


def crane_dimensions(layout: Layout) -> CraneDimensions:
    column_x = layout.cell_length / 2 + COLUMN_CLEARANCE_M + COLUMN_WIDTH_M / 2
    fork_top = layout.load_base_height()
    fork_bottom = min(
        RACK_MEMBER_THICKNESS_M / 2 + FORK_GAP_ABOVE_BEAM_M, fork_top - MINIMUM_FORK_THICKNESS_M
    )
    return CraneDimensions(
        height=layout.height,
        column_x=column_x,
        section_x=max(layout.cell_length / 4, layout.cell_length / 2 - SECTION_FROM_END_M),
        reach=(layout.aisle_width + layout.cell_width) / 2,
        fork_top=fork_top,
        fork_bottom=fork_bottom,
        plate_bottom=min(FLOOR_TIE_HEIGHT_M, fork_bottom - MINIMUM_PLATE_THICKNESS_M),
        fork_length=layout.aisle_width * FORK_LENGTH_SHARE,
        tine_spacing=layout.cell_length * TINE_SPACING_SHARE,
        frame_x=column_x - COLUMN_WIDTH_M / 2 - RAIL_WIDTH_M - END_FRAME_GAP_M - END_FRAME_M / 2,
        frame_height=max(MINIMUM_END_FRAME_HEIGHT_M, layout.cell_height * END_FRAME_HEIGHT_SHARE),
        cell_height=layout.cell_height,
    )


def _span(low: float, high: float) -> tuple[float, float]:
    """Returns the center and size of a span."""
    return (low + high) / 2, high - low


def _section(size: CraneDimensions, side: float, x: float, y: float, extension: float) -> Box:
    half_width = size.tine_spacing + STAGE_WIDTH_M * 1.5
    half_length = size.fork_length / 2
    z, depth = _span(-half_length + min(0.0, extension), half_length + max(0.0, extension))
    center_y, height = _span(size.fork_bottom, size.fork_top)
    return Box((x + side * size.section_x, y + center_y, z), (2 * half_width, height, depth))


def crane_boxes(
    layout: Layout,
    size: CraneDimensions,
    aisle: int,
    position: tuple[float, float],
    extension: float = 0.0,
    load_offset: float = 0.0,
    carrying: bool = False,
    load_size: Vector | None = None,
) -> dict[str, Box]:
    """Returns what a crane occupies at a position, by part, for selection."""
    x, y, z = layout.crane_world_position(aisle, position)
    column_y, column_height = _span(BOGIE_TOP_M, size.height - TOP_BEAM_HEIGHT_M)
    gear_y, gear_height = _span(0.0, TRAVEL_GEAR_HEIGHT_M)
    beam_y, beam_height = _span(size.height - TOP_BEAM_HEIGHT_M, size.height + TOP_ROLLER_HEIGHT_M)
    ladder_y, ladder_height = _span(BOGIE_TOP_M, size.height - TOP_BEAM_HEIGHT_M)
    frame_y, frame_height = _span(FLOOR_TIE_HEIGHT_M, FLOOR_TIE_HEIGHT_M + size.frame_height)
    plate_y, plate_height = _span(size.plate_bottom, size.fork_bottom)
    frame_width = END_FRAME_M + RAIL_WIDTH_M
    frame_offset = RAIL_WIDTH_M / 2
    boxes = {
        "TopBeam": Box(
            (x, beam_y, z),
            (2 * size.column_x + COLUMN_WIDTH_M, beam_height, TOP_ROLLER_DEPTH_M),
        ),
        "FloorTie": Box(
            (x, FLOOR_TIE_HEIGHT_M / 2, z),
            (2 * size.column_x, FLOOR_TIE_HEIGHT_M, FLOOR_TIE_DEPTH_M),
        ),
        "Cabinet": Box(
            (x + size.cabinet_x, TRAVEL_GEAR_HEIGHT_M + CABINET_HEIGHT_M / 2, z),
            (CABINET_WIDTH_M, CABINET_HEIGHT_M, CABINET_DEPTH_M),
        ),
        "Ladder": Box(
            (x + size.ladder_x, ladder_y, z),
            (LADDER_MEMBER_M, ladder_height, LADDER_WIDTH_M + LADDER_MEMBER_M),
        ),
        "Plate": Box(
            (x, y + plate_y, z),
            (2 * size.frame_x, plate_height, PLATE_DEPTH_M),
        ),
        "Section1": _section(size, -1.0, x, y, extension),
        "Section2": _section(size, 1.0, x, y, extension),
    }
    for name, side in (("Left", -1.0), ("Right", 1.0)):
        boxes[f"Column{name}"] = Box(
            (x + side * size.column_x, column_y, z),
            (COLUMN_WIDTH_M, column_height, COLUMN_DEPTH_M),
        )
        boxes[f"Rail{name}"] = Box(
            (x + size.rail_x(side), size.height / 2, z),
            (RAIL_WIDTH_M, size.height, RAIL_SPAN_M),
        )
        boxes[f"TravelGear{name}"] = Box(
            (x + size.bogie_x(side), gear_y, z),
            (BOGIE_LENGTH_M, gear_height, BOGIE_DEPTH_M),
        )
        boxes[f"EndFrame{name}"] = Box(
            (x + side * (size.frame_x + frame_offset), y + frame_y, z),
            (frame_width, frame_height, END_FRAME_DEPTH_M),
        )
    if carrying:
        shown = load_size or layout.load_size()
        boxes["Load"] = Box((x, y + size.fork_top + shown[1] / 2, z + load_offset), shown)
    return boxes
