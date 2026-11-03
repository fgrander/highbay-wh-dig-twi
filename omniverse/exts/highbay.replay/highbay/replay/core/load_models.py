"""Load units as USD text, with their origin on the floor at the center of the unit.

Each stack is one mesh, as many prims per unit would be repeated in up to 100,000 cells. Individual
sheets are not modeled: bands on a block of sheets stand for them. The sizes come from the data.
"""

from .crane_model import Model, indented, vector
from .load_definitions import LoadUnitType

BOARD_COLOR = (0.36, 0.22, 0.10)
SHEET_COLOR = (0.80, 0.82, 0.86)
SHEET_EDGE_COLOR = (0.42, 0.44, 0.48)
BASE_COLOR = (0.48, 0.33, 0.16)
BOARD_INSET_M = 0.004
BOARD_FILL = 0.97
SHEET_BANDS = 20
SHEET_ROUGHNESS = 0.25
WOOD_ROUGHNESS = 0.8

Point = tuple[float, float, float]
# The corners of a box's faces, with the outside to the viewer.
_FACES = (
    (0, 1, 3, 2),
    (4, 6, 7, 5),
    (0, 4, 5, 1),
    (2, 3, 7, 6),
    (0, 2, 6, 4),
    (1, 5, 7, 3),
)
_DOWN = 2
_UP = 3


def _linear(hex_color: str) -> tuple[float, float, float]:
    def channel(value: int) -> float:
        share = value / 255
        return share / 12.92 if share <= 0.04045 else ((share + 0.055) / 1.055) ** 2.4

    red, green, blue = (channel(int(hex_color[index : index + 2], 16)) for index in (1, 3, 5))
    return (red, green, blue)


class _Mesh:
    def __init__(self) -> None:
        self.points: list[Point] = []
        self.counts: list[int] = []
        self.indices: list[int] = []

    def add_box(self, low: Point, high: Point, faces: tuple[int, ...] = (0, 1, 2, 3, 4, 5)) -> int:
        """Adds a box with the given faces, and returns how many faces it added."""
        base = len(self.points)
        for x in (low[0], high[0]):
            for y in (low[1], high[1]):
                for z in (low[2], high[2]):
                    self.points.append((x, y, z))
        for face in faces:
            self.counts.append(4)
            self.indices.extend(base + corner for corner in _FACES[face])
        return len(faces)

    def text(self, name: str, material: str | None, children: str = "") -> str:
        lows = tuple(min(point[axis] for point in self.points) for axis in range(3))
        highs = tuple(max(point[axis] for point in self.points) for axis in range(3))
        schemas = ""
        binding = ""
        if material:
            schemas = ' (\n    prepend apiSchemas = ["MaterialBindingAPI"]\n)'
            binding = f"\n    rel material:binding = </Look/Materials/{material}>"
        points = ", ".join(vector(point) for point in self.points)
        counts = ", ".join(str(count) for count in self.counts)
        indices = ", ".join(str(index) for index in self.indices)
        return f"""def Mesh "{name}"{schemas}
{{
    float3[] extent = [{vector(lows)}, {vector(highs)}]
    int[] faceVertexCounts = [{counts}]
    int[] faceVertexIndices = [{indices}]
    point3f[] points = [{points}]
    uniform token subdivisionScheme = "none"{binding}{children}
}}"""


def _subset(name: str, faces: list[int], material: str) -> str:
    indices = ", ".join(str(face) for face in faces)
    return f"""def GeomSubset "{name}" (
    prepend apiSchemas = ["MaterialBindingAPI"]
)
{{
    uniform token elementType = "face"
    uniform token familyName = "materialBind"
    int[] indices = [{indices}]
    rel material:binding = </Look/Materials/{material}>
}}"""


def board_stack_usda(unit: LoadUnitType, length_m: float) -> str:
    """Returns a stack with one box per board. Every second one lies slightly inward to show."""
    half_length = length_m / 2
    half_width = unit.width_m / 2
    mesh = _Mesh()
    for board in range(unit.count):
        inset = BOARD_INSET_M if board % 2 else 0.0
        bottom = board * unit.thickness_m
        fill = 1.0 if board == unit.count - 1 else BOARD_FILL
        mesh.add_box(
            (-half_length + inset, bottom, -half_width + inset),
            (half_length - inset, bottom + unit.thickness_m * fill, half_width - inset),
        )
    color = _linear(unit.color) if unit.color else BOARD_COLOR
    materials = {"Board": (color, 0.0, WOOD_ROUGHNESS)}
    return Model([mesh.text("Boards", "Board")], materials).text()


def paper_pallet_usda(unit: LoadUnitType, length_m: float) -> str:
    """Returns a block of sheets on a base board, with bands that stand for the sheets."""
    half_length = length_m / 2
    half_width = unit.width_m / 2
    bottom = unit.base_thickness_m
    height = unit.count * unit.thickness_m
    mesh = _Mesh()
    light: list[int] = []
    dark: list[int] = []
    face = 0
    for band in range(SHEET_BANDS):
        faces = [0, 1, 4, 5]
        if band == 0:
            faces.append(_DOWN)
        if band == SHEET_BANDS - 1:
            faces.append(_UP)
        added = mesh.add_box(
            (-half_length, bottom + height * band / SHEET_BANDS, -half_width),
            (half_length, bottom + height * (band + 1) / SHEET_BANDS, half_width),
            tuple(faces),
        )
        (light if band % 2 else dark).extend(range(face, face + added))
        face += added
    subsets = "\n\n" + indented(_subset("LightBands", light, "SheetLight"))
    subsets += "\n\n" + indented(_subset("DarkBands", dark, "SheetDark"))
    materials = {
        "SheetLight": (_linear(unit.color) if unit.color else SHEET_COLOR, 0.0, SHEET_ROUGHNESS),
        "SheetDark": (
            _linear(unit.edge_color) if unit.edge_color else SHEET_EDGE_COLOR,
            0.0,
            SHEET_ROUGHNESS,
        ),
        "BaseBoard": (BASE_COLOR, 0.0, WOOD_ROUGHNESS),
    }
    base = _Mesh()
    base.add_box((-half_length, 0.0, -half_width), (half_length, bottom, half_width))
    parts = [base.text("Base", "BaseBoard"), mesh.text("Sheets", None, subsets)]
    return Model(parts, materials).text()
