"""Writes a two-column stacker crane's mast and carriage as USD files, sized from a warehouse.

Usage: uv run python omniverse/models/build_crane_model.py RUN_FOLDER OUTPUT_FOLDER

This is a general crane with placeholder dimensions, not a manufacturer's model. It uses only the
standard library, and identical inputs give identical files. Each file follows the rules in
omniverse/exts/highbay.replay/README.md: meters, Y up, x along the aisle, z across it, and the
origin at the center of the simple shape that it replaces.

The load travels between two columns. The carriage has two fork sections, Section1 and Section2,
that extend across the aisle separately, in both directions. Each has the telescopic stages Base,
Middle, and Top. To extend a section by a distance, move its Top by that distance along z, and its
Middle by half of it. Parts without a material show the crane's activity color, which they inherit
from the top prim.
"""

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

LOAD_SIZE_SHARE = 0.85

# Materials: diffuse color (linear), metallic, roughness.
MATERIALS = {
    "CraneBlue": ((0.03, 0.13, 0.32), 0.2, 0.45),
    "DarkSteel": ((0.05, 0.055, 0.06), 0.8, 0.4),
    "BrightSteel": ((0.55, 0.56, 0.58), 0.9, 0.3),
    "SafetyYellow": ((0.85, 0.55, 0.02), 0.0, 0.5),
    "CabinetGray": ((0.45, 0.47, 0.49), 0.1, 0.6),
}

COLUMN_WIDTH_M = 0.34
COLUMN_DEPTH_M = 0.5
COLUMN_CLEARANCE_M = 0.25
BOGIE_LENGTH_M = 1.1
BOGIE_HEIGHT_M = 0.42
BOGIE_DEPTH_M = 0.7
WHEEL_RADIUS_M = 0.2
WHEEL_WIDTH_M = 0.12
TIE_HEIGHT_M = 0.04
TOP_BEAM_HEIGHT_M = 0.3
LADDER_WIDTH_M = 0.42
RUNG_SPACING_M = 0.3
END_FRAME_M = 0.12
# Everything under the load has to fit in this height, as cells at floor level exist.
FORK_SPACE_M = 0.075
PLATE_HEIGHT_M = 0.015
STAGE_WIDTH_M = 0.07


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
    radius = WHEEL_RADIUS_M
    half = WHEEL_WIDTH_M / 2
    return f"""def Cylinder "{name}"{schemas}
{{
    uniform token axis = "Z"
    double height = {WHEEL_WIDTH_M}
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


def column_x(load_length: float) -> float:
    """Returns how far each column stands from the crane's center, on either side of the load."""
    return load_length / 2 + COLUMN_CLEARANCE_M + COLUMN_WIDTH_M / 2


def _column(side: str, x: float, inner: float, height: float) -> list[str]:
    floor = -height / 2
    bogie_top = WHEEL_RADIUS_M + BOGIE_HEIGHT_M
    column_height = height - bogie_top
    column_y = floor + bogie_top + column_height / 2
    rail_x = x + inner * (COLUMN_WIDTH_M / 2 + 0.03)
    strip_z = COLUMN_DEPTH_M / 2 + 0.011
    parts = [
        box(
            f"Column{side}",
            (x, column_y, 0.0),
            (COLUMN_WIDTH_M, column_height, COLUMN_DEPTH_M),
            "CraneBlue",
        ),
        box(
            f"Rail{side}Front", (rail_x, column_y, 0.15), (0.06, column_height, 0.08), "BrightSteel"
        ),
        box(
            f"Rail{side}Back", (rail_x, column_y, -0.15), (0.06, column_height, 0.08), "BrightSteel"
        ),
        # A strip with no material shows the crane's activity color along the column.
        box(
            f"Status{side}Front",
            (x, column_y, strip_z),
            (COLUMN_WIDTH_M * 0.5, column_height, 0.02),
            None,
        ),
        box(
            f"Status{side}Back",
            (x, column_y, -strip_z),
            (COLUMN_WIDTH_M * 0.5, column_height, 0.02),
            None,
        ),
    ]
    bogie_x = x - inner * (BOGIE_LENGTH_M - COLUMN_WIDTH_M) / 2
    bogie_y = floor + WHEEL_RADIUS_M + BOGIE_HEIGHT_M / 2
    parts += [
        box(
            f"Bogie{side}",
            (bogie_x, bogie_y, 0.0),
            (BOGIE_LENGTH_M, BOGIE_HEIGHT_M, BOGIE_DEPTH_M),
            "CraneBlue",
        ),
        box(
            f"BogieStripe{side}",
            (bogie_x, floor + bogie_top + 0.015, 0.0),
            (BOGIE_LENGTH_M, 0.03, BOGIE_DEPTH_M),
            "SafetyYellow",
        ),
    ]
    wheel_z = BOGIE_DEPTH_M / 2 - WHEEL_WIDTH_M / 2
    for index, offset in enumerate((-0.3, 0.3), start=1):
        for label, z in (("Front", wheel_z), ("Back", -wheel_z)):
            center = (bogie_x + offset, floor + WHEEL_RADIUS_M, z)
            parts.append(wheel(f"Wheel{side}{label}{index}", center, "DarkSteel"))
    return parts


def build_mast(height: float, load_length: float) -> Model:
    """The part that travels along the aisle. Its origin is at half the warehouse's height."""
    x = column_x(load_length)
    floor = -height / 2
    # The left column's inner side faces +x, and the right column's faces -x.
    parts = [*_column("Left", -x, 1.0, height), *_column("Right", x, -1.0, height)]

    # A low plate joins the bogies, as the load has to reach cells at floor level between them.
    parts.append(
        box(
            "FloorTie",
            (0.0, floor + TIE_HEIGHT_M / 2, 0.0),
            (2 * x, TIE_HEIGHT_M, 0.3),
            "DarkSteel",
        )
    )

    span = 2 * x + COLUMN_WIDTH_M
    parts.append(
        box(
            "TopBeam",
            (0.0, height / 2 - TOP_BEAM_HEIGHT_M / 2, 0.0),
            (span, TOP_BEAM_HEIGHT_M, COLUMN_DEPTH_M),
            "DarkSteel",
        )
    )
    for label, roller_x in (("Left", -x), ("Right", x)):
        for side, z in (("Front", 0.32), ("Back", -0.32)):
            parts.append(
                box(
                    f"TopRoller{label}{side}",
                    (roller_x, height / 2 + 0.05, z),
                    (0.16, 0.1, 0.08),
                    "BrightSteel",
                )
            )

    cabinet_x = -x - BOGIE_LENGTH_M + COLUMN_WIDTH_M + 0.2
    bogie_top = floor + WHEEL_RADIUS_M + BOGIE_HEIGHT_M + 0.03
    parts.append(box("Cabinet", (cabinet_x, bogie_top + 0.55, 0.0), (0.4, 1.1, 0.5), "CabinetGray"))

    # A ladder on the outer side of the left column.
    ladder_x = -x - COLUMN_WIDTH_M / 2 - 0.04
    ladder_height = height - WHEEL_RADIUS_M - BOGIE_HEIGHT_M - TOP_BEAM_HEIGHT_M
    ladder_y = height / 2 - TOP_BEAM_HEIGHT_M - ladder_height / 2
    for side, z in (("A", -LADDER_WIDTH_M / 2), ("B", LADDER_WIDTH_M / 2)):
        parts.append(
            box(
                f"Ladder{side}",
                (ladder_x, ladder_y, z),
                (0.04, ladder_height, 0.04),
                "SafetyYellow",
            )
        )
    for rung in range(int(ladder_height / RUNG_SPACING_M)):
        y = ladder_y - ladder_height / 2 + (rung + 0.5) * RUNG_SPACING_M
        parts.append(
            box(
                f"Rung{rung:03d}",
                (ladder_x, y, 0.0),
                (0.025, 0.025, LADDER_WIDTH_M),
                "SafetyYellow",
            )
        )
    return Model(parts)


def _section(name: str, center_x: float, tine_spacing: float, fork_length: float) -> str:
    """A fork section with two tines, each of three stages that slide across the aisle."""
    stage_y = PLATE_HEIGHT_M + (FORK_SPACE_M - PLATE_HEIGHT_M) / 2
    stage_height = FORK_SPACE_M - PLATE_HEIGHT_M
    stages = []
    for stage, offset, material in (
        ("Base", -STAGE_WIDTH_M, "DarkSteel"),
        ("Middle", 0.0, "CraneBlue"),
        ("Top", STAGE_WIDTH_M, "BrightSteel"),
    ):
        tines = [
            box(
                f"Tine{label}",
                (center_x + side * tine_spacing + side * offset, stage_y, 0.0),
                (STAGE_WIDTH_M, stage_height, fork_length),
                material,
            )
            for label, side in (("A", -1), ("B", 1))
        ]
        stages.append(group(stage, tines))
    return group(name, stages)


def build_carriage(load_length: float, load_height: float, aisle_width: float) -> Model:
    """The part that moves up the columns. Its origin is at floor level below the load."""
    x = column_x(load_length)
    frame_x = x - COLUMN_WIDTH_M / 2 - 0.06 - END_FRAME_M / 2
    frame_height = max(0.6, load_height * 0.7)
    frame_y = frame_height / 2
    parts = []
    for side, sign in (("Left", -1.0), ("Right", 1.0)):
        parts.append(
            box(
                f"EndFrame{side}",
                (sign * frame_x, frame_y, 0.0),
                (END_FRAME_M, frame_height, 0.6),
                "CraneBlue",
            )
        )
        roller_x = sign * (frame_x + END_FRAME_M / 2 + 0.03)
        for label, z in (("Front", 0.15), ("Back", -0.15)):
            for level, y in (("Low", 0.1), ("High", frame_height - 0.1)):
                parts.append(
                    box(
                        f"Roller{side}{label}{level}",
                        (roller_x, y, z),
                        (0.06, 0.12, 0.1),
                        "BrightSteel",
                    )
                )
        # A strip with no material shows the crane's activity color on the moving part.
        for label, z in (("Front", 0.31), ("Back", -0.31)):
            parts.append(
                box(
                    f"Status{side}{label}",
                    (sign * frame_x, frame_y, z),
                    (END_FRAME_M * 0.6, frame_height * 0.8, 0.02),
                    None,
                )
            )

    # A thin plate carries the sections between the two end frames.
    parts.append(
        box(
            "Plate", (0.0, PLATE_HEIGHT_M / 2, 0.0), (2 * frame_x, PLATE_HEIGHT_M, 0.4), "DarkSteel"
        )
    )

    fork_length = aisle_width * 0.85
    section_x = load_length * 0.25
    tine_spacing = load_length * 0.09
    parts.append(_section("Section1", -section_x, tine_spacing, fork_length))
    parts.append(_section("Section2", section_x, tine_spacing, fork_length))
    return Model(parts)


def main(run_folder: str, output_folder: str) -> None:
    recording = json.loads((Path(run_folder) / "replay.json").read_text(encoding="utf-8"))
    layout = recording["warehouse"]["layout"]
    cell = layout["cell"]
    height = layout["levels_per_rack"] * cell["height_m"]
    load_length = cell["length_m"] * LOAD_SIZE_SHARE
    load_height = cell["height_m"] * LOAD_SIZE_SHARE

    output = Path(output_folder)
    output.mkdir(parents=True, exist_ok=True)
    files = {
        "crane_mast.usda": build_mast(height, load_length),
        "crane_carriage.usda": build_carriage(load_length, load_height, cell["width_m"]),
    }
    for name, model in files.items():
        (output / name).write_text(model.text(), encoding="utf-8", newline="\n")
        print(f"{output / name}: {len(model.parts)} parts")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    main(sys.argv[1], sys.argv[2])
