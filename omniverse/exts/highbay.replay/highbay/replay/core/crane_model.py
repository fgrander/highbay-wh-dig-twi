"""A two-column stacker crane's mast and carriage as USD text, sized from a warehouse.

This is a general crane with placeholder dimensions, not a manufacturer's model. Identical inputs
give identical text. It follows the rules for looks in the extension's README: meters, Y up, x along
the aisle, z across it, and the origin at the center of the simple shape that it replaces.

The load travels between two columns. The carriage has two fork sections, Section1 and Section2,
that can extend across the aisle separately, in both directions. Each has the telescopic stages
Base, Middle, and Top. To extend a section by a distance, move its Top by that distance along z, and
its Middle by half of it. The columns and the carriage's end frames have no material, so they show
the crane's activity color, which they inherit from the top prim. Looking along an aisle, little
else of a crane can be seen.
"""

from dataclasses import dataclass, field

from . import crane_dimensions as sizes
from .crane_dimensions import CraneDimensions, crane_dimensions
from .layout import Layout

# Materials: diffuse color (linear), metallic, roughness.
MATERIALS = {
    "CraneBlue": ((0.03, 0.13, 0.32), 0.2, 0.45),
    "DarkSteel": ((0.05, 0.055, 0.06), 0.8, 0.4),
    "BrightSteel": ((0.55, 0.56, 0.58), 0.9, 0.3),
    "SafetyYellow": ((0.85, 0.55, 0.02), 0.0, 0.5),
    "CabinetGray": ((0.45, 0.47, 0.49), 0.1, 0.6),
}
RUNG_SPACING_M = 0.3
RUNG_THICKNESS_M = 0.025
WHEEL_OFFSET_M = 0.3
ROLLER_HEIGHT_M = 0.12
ROLLER_DEPTH_M = 0.1
ROLLER_Z_M = 0.15
TOP_ROLLER_WIDTH_M = 0.16
TOP_ROLLER_DEPTH_M = 0.08


def _vector(values: tuple[float, ...]) -> str:
    return "(" + ", ".join(f"{value:.6g}" for value in values) + ")"


def _binding(material: str | None) -> tuple[str, str]:
    if material is None:
        return "", ""
    schemas = ' (\n    prepend apiSchemas = ["MaterialBindingAPI"]\n)'
    binding = f"\n    rel material:binding = </Look/Materials/{material}>"
    return schemas, binding


def box(
    name: str,
    center: tuple[float, float, float],
    size: tuple[float, float, float],
    material: str | None,
) -> str:
    schemas, binding = _binding(material)
    return f"""def Cube "{name}"{schemas}
{{
    double size = 1
    float3[] extent = [(-0.5, -0.5, -0.5), (0.5, 0.5, 0.5)]{binding}
    double3 xformOp:translate = {_vector(center)}
    float3 xformOp:scale = {_vector(size)}
    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
}}"""


def wheel(name: str, center: tuple[float, float, float], material: str) -> str:
    schemas, binding = _binding(material)
    radius = sizes.WHEEL_RADIUS_M
    half = sizes.WHEEL_WIDTH_M / 2
    return f"""def Cylinder "{name}"{schemas}
{{
    uniform token axis = "Z"
    double height = {sizes.WHEEL_WIDTH_M}
    double radius = {radius}
    float3[] extent = [(-{radius}, -{radius}, -{half}), ({radius}, {radius}, {half})]{binding}
    double3 xformOp:translate = {_vector(center)}
    uniform token[] xformOpOrder = ["xformOp:translate"]
}}"""


def _indented(text: str) -> str:
    return "\n".join("    " + line if line else line for line in text.splitlines())


def group(name: str, parts: list[str]) -> str:
    """Returns a movable group of parts, whose translate starts at zero."""
    children = "\n\n".join(_indented(part) for part in parts)
    return f"""def Xform "{name}"
{{
    double3 xformOp:translate = (0, 0, 0)
    uniform token[] xformOpOrder = ["xformOp:translate"]

{children}
}}"""


@dataclass
class Model:
    parts: list[str] = field(default_factory=list)

    def text(self) -> str:
        materials = "\n\n".join(
            f"""def Material "{name}"
{{
    token outputs:surface.connect = </Look/Materials/{name}/Shader.outputs:surface>

    def Shader "Shader"
    {{
        uniform token info:id = "UsdPreviewSurface"
        color3f inputs:diffuseColor = {_vector(color)}
        float inputs:metallic = {metallic}
        float inputs:roughness = {roughness}
        token outputs:surface
    }}
}}"""
            for name, (color, metallic, roughness) in MATERIALS.items()
        )
        scope = f'def Scope "Materials"\n{{\n{_indented(materials)}\n}}'
        body = "\n\n".join(_indented(part) for part in [scope, *self.parts])
        return f"""#usda 1.0
(
    defaultPrim = "Look"
    metersPerUnit = 1
    upAxis = "Y"
)

def Xform "Look"
{{
{body}
}}
"""


def _column(name: str, side: float, size: CraneDimensions) -> list[str]:
    """One column with its rails, status strips, and travel gear. Heights are from mid-mast."""
    x = side * size.column_x
    floor = -size.height / 2
    # Columns end below the top beam, as faces in the same place flicker when rendered.
    column_height = size.height - sizes.BOGIE_TOP_M - sizes.TOP_BEAM_HEIGHT_M
    column_y = floor + sizes.BOGIE_TOP_M + column_height / 2
    rail_z = sizes.RAIL_SPAN_M / 2 - 0.04
    parts = [
        box(
            f"Column{name}",
            (x, column_y, 0.0),
            (sizes.COLUMN_WIDTH_M, column_height, sizes.COLUMN_DEPTH_M),
            None,
        ),
    ]
    # Rails reach down to the floor, so that the carriage has them at the lowest level.
    for label, z in (("Front", rail_z), ("Back", -rail_z)):
        parts.append(
            box(
                f"Rail{name}{label}",
                (size.rail_x(side), 0.0, z),
                (sizes.RAIL_WIDTH_M, size.height, 0.08),
                "BrightSteel",
            )
        )
    bogie_x = size.bogie_x(side)
    bogie_y = floor + sizes.WHEEL_RADIUS_M + sizes.BOGIE_HEIGHT_M / 2
    parts += [
        box(
            f"Bogie{name}",
            (bogie_x, bogie_y, 0.0),
            (sizes.BOGIE_LENGTH_M, sizes.BOGIE_HEIGHT_M, sizes.BOGIE_DEPTH_M),
            "CraneBlue",
        ),
        box(
            f"BogieStripe{name}",
            (bogie_x, floor + sizes.BOGIE_TOP_M + sizes.BOGIE_STRIPE_HEIGHT_M / 2, 0.0),
            (sizes.BOGIE_LENGTH_M, sizes.BOGIE_STRIPE_HEIGHT_M, sizes.BOGIE_DEPTH_M),
            "SafetyYellow",
        ),
    ]
    wheel_z = sizes.BOGIE_DEPTH_M / 2 - sizes.WHEEL_WIDTH_M / 2
    for index, offset in enumerate((-WHEEL_OFFSET_M, WHEEL_OFFSET_M), start=1):
        for label, z in (("Front", wheel_z), ("Back", -wheel_z)):
            center = (bogie_x + offset, floor + sizes.WHEEL_RADIUS_M, z)
            parts.append(wheel(f"Wheel{name}{label}{index}", center, "DarkSteel"))
    return parts


def _build_mast(size: CraneDimensions) -> Model:
    """The part that travels along the aisle. Its origin is at half the warehouse's height."""
    x = size.column_x
    floor = -size.height / 2
    top = size.height / 2
    parts = [*_column("Left", -1.0, size), *_column("Right", 1.0, size)]

    # A low plate joins the bogies, as the load has to reach cells at floor level between them.
    parts.append(
        box(
            "FloorTie",
            (0.0, floor + sizes.FLOOR_TIE_HEIGHT_M / 2, 0.0),
            (2 * x, sizes.FLOOR_TIE_HEIGHT_M, sizes.FLOOR_TIE_DEPTH_M),
            "DarkSteel",
        )
    )
    parts.append(
        box(
            "TopBeam",
            (0.0, top - sizes.TOP_BEAM_HEIGHT_M / 2, 0.0),
            (2 * x + sizes.COLUMN_WIDTH_M, sizes.TOP_BEAM_HEIGHT_M, sizes.COLUMN_DEPTH_M),
            "DarkSteel",
        )
    )
    roller_z = sizes.TOP_ROLLER_DEPTH_M / 2 - TOP_ROLLER_DEPTH_M / 2
    for label, roller_x in (("Left", -x), ("Right", x)):
        for side, z in (("Front", roller_z), ("Back", -roller_z)):
            parts.append(
                box(
                    f"TopRoller{label}{side}",
                    (roller_x, top + sizes.TOP_ROLLER_HEIGHT_M / 2, z),
                    (TOP_ROLLER_WIDTH_M, sizes.TOP_ROLLER_HEIGHT_M, TOP_ROLLER_DEPTH_M),
                    "BrightSteel",
                )
            )
    parts.append(
        box(
            "Cabinet",
            (
                size.cabinet_x,
                floor + sizes.TRAVEL_GEAR_HEIGHT_M + sizes.CABINET_HEIGHT_M / 2,
                0.0,
            ),
            (sizes.CABINET_WIDTH_M, sizes.CABINET_HEIGHT_M, sizes.CABINET_DEPTH_M),
            "CabinetGray",
        )
    )

    # A ladder on the outer side of the left column.
    ladder_height = size.ladder_height
    ladder_y = top - sizes.TOP_BEAM_HEIGHT_M - ladder_height / 2
    for side, z in (("A", -sizes.LADDER_WIDTH_M / 2), ("B", sizes.LADDER_WIDTH_M / 2)):
        parts.append(
            box(
                f"Ladder{side}",
                (size.ladder_x, ladder_y, z),
                (sizes.LADDER_MEMBER_M, ladder_height, sizes.LADDER_MEMBER_M),
                "SafetyYellow",
            )
        )
    for rung in range(int(ladder_height / RUNG_SPACING_M)):
        y = ladder_y - ladder_height / 2 + (rung + 0.5) * RUNG_SPACING_M
        parts.append(
            box(
                f"Rung{rung:03d}",
                (size.ladder_x, y, 0.0),
                (RUNG_THICKNESS_M, RUNG_THICKNESS_M, sizes.LADDER_WIDTH_M),
                "SafetyYellow",
            )
        )
    return Model(parts)


def _section(name: str, side: float, size: CraneDimensions) -> str:
    """A fork section with two tines, each of three stages that slide across the aisle."""
    center_x = side * size.section_x
    stage_y = (size.fork_bottom + size.fork_top) / 2
    stage_height = size.fork_top - size.fork_bottom
    stages = []
    for stage, offset, material in (
        ("Base", -sizes.STAGE_WIDTH_M, "DarkSteel"),
        ("Middle", 0.0, "CraneBlue"),
        ("Top", sizes.STAGE_WIDTH_M, "BrightSteel"),
    ):
        tines = [
            box(
                f"Tine{label}",
                (center_x + tine * (size.tine_spacing + offset), stage_y, 0.0),
                (sizes.STAGE_WIDTH_M, stage_height, size.fork_length),
                material,
            )
            for label, tine in (("A", -1), ("B", 1))
        ]
        stages.append(group(stage, tines))
    return group(name, stages)


def _build_carriage(size: CraneDimensions) -> Model:
    """The part that moves up the columns. Its origin is at the floor of the cell it stands at."""
    frame_bottom = sizes.FLOOR_TIE_HEIGHT_M
    frame_y = frame_bottom + size.frame_height / 2
    parts = []
    for name, side in (("Left", -1.0), ("Right", 1.0)):
        frame_x = side * size.frame_x
        parts.append(
            box(
                f"EndFrame{name}",
                (frame_x, frame_y, 0.0),
                (sizes.END_FRAME_M, size.frame_height, sizes.END_FRAME_DEPTH_M),
                None,
            )
        )
        roller_x = side * (size.frame_x + sizes.END_FRAME_M / 2 + sizes.ROLLER_WIDTH_M / 2)
        for label, z in (("Front", ROLLER_Z_M), ("Back", -ROLLER_Z_M)):
            for level, y in (
                ("Low", frame_bottom + ROLLER_HEIGHT_M / 2),
                ("High", frame_bottom + size.frame_height - ROLLER_HEIGHT_M / 2),
            ):
                parts.append(
                    box(
                        f"Roller{name}{label}{level}",
                        (roller_x, y, z),
                        (sizes.ROLLER_WIDTH_M, ROLLER_HEIGHT_M, ROLLER_DEPTH_M),
                        "BrightSteel",
                    )
                )

    # A thin plate carries the sections between the two end frames.
    plate_height = size.fork_bottom - size.plate_bottom
    parts.append(
        box(
            "Plate",
            (0.0, size.plate_bottom + plate_height / 2, 0.0),
            (2 * size.frame_x, plate_height, sizes.PLATE_DEPTH_M),
            "DarkSteel",
        )
    )
    parts.append(_section("Section1", -1.0, size))
    parts.append(_section("Section2", 1.0, size))
    return Model(parts)


def crane_mast_usda(layout: Layout) -> str:
    return _build_mast(crane_dimensions(layout)).text()


def crane_carriage_usda(layout: Layout) -> str:
    return _build_carriage(crane_dimensions(layout)).text()
