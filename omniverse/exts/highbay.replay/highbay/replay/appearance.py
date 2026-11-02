"""The only module that decides how objects look.

To use detailed models, replace these functions: each creates the object for one type from
dimensions, and the rest of the extension only places it.
"""

from typing import Any

from pxr import Gf, UsdGeom, UsdLux

from .core.layout import Bounds, Layout, Vector

# Kept apart from the crane activity colors below, so that the two are not confused.
ARTICLE_COLORS = (
    "#c9b27c",
    "#5aa89a",
    "#b5587a",
    "#8fae4e",
    "#7d8fb3",
    "#a67c52",
    "#c7c24a",
    "#5f7f5f",
)
ACTIVITY_COLORS = {
    "moving_empty": "#2f6fd6",
    "moving_loaded": "#e8842c",
    "handling": "#8a4fc7",
    "idle": "#8a8f96",
}
RACK_COLOR = "#7c8794"
INBOUND_COLOR = "#3fae5a"
OUTBOUND_COLOR = "#d35454"
FLOOR_COLOR = "#e4e7ea"
HIGHLIGHT_COLOR = "#000000"
LOAD_SIZE_SHARE = 0.85
CRANE_THICKNESS_SHARE = 0.5
RACK_MEMBER_THICKNESS_M = 0.08
FLOOR_THICKNESS_M = 0.1
DOME_INTENSITY = 350.0
SUN_INTENSITY = 400.0


def color(hex_color: str) -> Gf.Vec3f:
    """Returns the linear color of a sRGB hex color, which is what the renderer expects."""

    def linear(channel: int) -> float:
        value = channel / 255
        return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4

    return Gf.Vec3f(*(linear(int(hex_color[i : i + 2], 16)) for i in (1, 3, 5)))


def article_prototype(index: int) -> int:
    """Returns the prototype of an article, from a fixed sequence in `articles` order."""
    return index % len(ARTICLE_COLORS)


def activity_color(activity: str) -> Gf.Vec3f:
    """Returns the color of a crane doing an activity."""
    return color(ACTIVITY_COLORS[activity])


def _box(stage: Any, path: str, size: Vector, center: Vector, box_color: Gf.Vec3f) -> Any:
    cube = UsdGeom.Cube.Define(stage, path)
    cube.CreateSizeAttr(1.0)
    cube.CreateExtentAttr([Gf.Vec3f(-0.5), Gf.Vec3f(0.5)])
    cube.CreateDisplayColorAttr([box_color])
    cube.AddTranslateOp().Set(Gf.Vec3d(*center))
    cube.AddScaleOp().Set(Gf.Vec3f(*size))
    return cube


def load_size(layout: Layout) -> Vector:
    return (
        layout.cell_length * LOAD_SIZE_SHARE,
        layout.cell_height * LOAD_SIZE_SHARE,
        layout.cell_width * LOAD_SIZE_SHARE,
    )


def create_lights(stage: Any, dome_path: str, sun_path: str) -> None:
    UsdLux.DomeLight.Define(stage, dome_path).CreateIntensityAttr(DOME_INTENSITY)
    sun = UsdLux.DistantLight.Define(stage, sun_path)
    sun.CreateIntensityAttr(SUN_INTENSITY)
    sun.CreateAngleAttr(1.0)
    UsdGeom.Xformable(sun).AddRotateXYZOp().Set(Gf.Vec3f(-55.0, 30.0, 0.0))


def create_floor(stage: Any, path: str, bounds: Bounds) -> None:
    """Creates the floor below the warehouse."""
    margin = max(bounds.max[0] - bounds.min[0], bounds.max[2] - bounds.min[2]) * 0.05
    _box(
        stage,
        path,
        (
            bounds.max[0] - bounds.min[0] + margin * 2,
            FLOOR_THICKNESS_M,
            bounds.max[2] - bounds.min[2] + margin * 2,
        ),
        (
            (bounds.min[0] + bounds.max[0]) / 2,
            -FLOOR_THICKNESS_M / 2,
            (bounds.min[2] + bounds.max[2]) / 2,
        ),
        color(FLOOR_COLOR),
    )


def create_load_prototypes(stage: Any, instancer_path: str, layout: Layout) -> list[str]:
    """Creates one load unit shape per article color, centered on its origin."""
    paths = []
    for index, article_color in enumerate(ARTICLE_COLORS):
        path = f"{instancer_path}/Load_{index}"
        _box(stage, path, load_size(layout), (0.0, 0.0, 0.0), color(article_color))
        paths.append(path)
    return paths


def create_rack_prototypes(stage: Any, instancer_path: str, layout: Layout) -> tuple[str, str]:
    """Creates an upright and a beam of a rack, centered on their origins."""
    thickness = RACK_MEMBER_THICKNESS_M
    upright = f"{instancer_path}/Upright"
    beam = f"{instancer_path}/Beam"
    _box(stage, upright, (thickness, layout.height, thickness), (0, 0, 0), color(RACK_COLOR))
    _box(stage, beam, (layout.length, thickness, thickness), (0, 0, 0), color(RACK_COLOR))
    return upright, beam


def create_crane(stage: Any, path: str, layout: Layout) -> None:
    """Creates a crane: a mast that moves along the aisle, and a carriage that moves up it."""
    thickness = layout.cell_width * CRANE_THICKNESS_SHARE
    idle = activity_color("idle")
    crane = UsdGeom.Xform.Define(stage, path)
    crane.AddTranslateOp().Set(Gf.Vec3d(0.0))
    _box(
        stage,
        f"{path}/Mast",
        (layout.cell_length * 0.12, layout.height, thickness),
        (0.0, layout.height / 2, 0.0),
        idle,
    )
    carriage = UsdGeom.Xform.Define(stage, f"{path}/Carriage")
    carriage.AddTranslateOp().Set(Gf.Vec3d(0.0))
    _box(
        stage,
        f"{path}/Carriage/Platform",
        (layout.cell_length * 0.9, layout.cell_height * 0.1, thickness * 1.3),
        (0.0, 0.0, 0.0),
        idle,
    )
    size = load_size(layout)
    carried = _box(
        stage,
        f"{path}/Carriage/CarriedLoad",
        size,
        (0.0, size[1] / 2 + layout.cell_height * 0.05, 0.0),
        color(ARTICLE_COLORS[0]),
    )
    carried.CreateVisibilityAttr(UsdGeom.Tokens.invisible)


def create_transfer_point(
    stage: Any, path: str, layout: Layout, role: str, position: tuple[float, float]
) -> None:
    """Creates a flat marker for a transfer point at an (x, z) position."""
    size = min(layout.cell_length, layout.cell_width) * 0.8
    _box(
        stage,
        path,
        (size, size * 0.1, size / 2),
        (position[0], size * 0.05, position[1]),
        color(INBOUND_COLOR if role == "inbound" else OUTBOUND_COLOR),
    )


def create_highlight(stage: Any, path: str) -> None:
    """Creates the empty group that marks a selected object, hidden with no selection."""
    highlight = UsdGeom.Xform.Define(stage, path)
    highlight.AddTranslateOp().Set(Gf.Vec3d(0.0))
    highlight.CreateVisibilityAttr(UsdGeom.Tokens.invisible)


def article_color(index: int) -> Gf.Vec3f:
    return color(ARTICLE_COLORS[article_prototype(index)])
