"""Builds the USD scene from a warehouse description, and updates it from run states.

How objects look is left to appearance.py. There are no timestamps or machine details in a built
scene, so identical data gives an identical scene.
"""

import math
from typing import Any

from pxr import Gf, Sdf, UsdGeom, Vt

from . import appearance
from .core.crane_dimensions import crane_boxes, crane_dimensions
from .core.fork_motion import REST, ForkPose, fork_pose
from .core.layout import Box, Vector, create_layout
from .core.state_source import CellChanges, RunState, StateSource, WarehouseDescription

WORLD = "/World"
LOADS = "/World/Loads"
RACKS = "/World/Racks"
CRANES = "/World/Cranes"
CAMERA = "/World/Camera"
SELECTION = "/World/Selection"
AISLE_LIGHTS = "/World/AisleLights"
MODELS_DETAILED = "detailed"
SECTIONS = ("Section1", "Section2")
TRANSFER_ROLES = ("inbound", "outbound")
ENDS = ("left", "right")
# Steep and nearly along the aisles, so that stored stock does not hide the cranes.
VIEW_DIRECTION = Gf.Vec3d(0.3, 0.9, 0.15).GetNormalized()
FOCAL_LENGTH_MM = 18.0
HORIZONTAL_APERTURE_MM = 20.955
VERTICAL_APERTURE_MM = 15.2908
WIDEST_VIEWPORT_ASPECT = 2.0


class _Crane:
    """The attribute specs of one crane, for fast writes, with what they currently hold."""

    def __init__(self, stage: Any, aisle: int) -> None:
        path = f"{CRANES}/Aisle_{aisle}"
        spec = stage.GetRootLayer().GetAttributeAtPath
        self.translate = spec(f"{path}.xformOp:translate")
        self.carriage = spec(f"{path}/Carriage.xformOp:translate")
        self.colors = (
            spec(f"{path}/Mast.primvars:displayColor"),
            spec(f"{path}/Carriage/Platform.primvars:displayColor"),
        )
        self.carried_visibility = spec(f"{path}/Carriage/CarriedLoad.visibility")
        self.carried_color = spec(f"{path}/Carriage/CarriedLoad.primvars:displayColor")
        self.carried_positions = spec(f"{path}/Carriage/CarriedLoad.positions")
        self.carried_prototypes = spec(f"{path}/Carriage/CarriedLoad.protoIndices")
        self.fork_stages = [
            self._writable(
                stage, f"{path}/Carriage/Platform/{section}/{stage_name}.xformOp:translate"
            )
            for section in SECTIONS
            for stage_name in ("Middle", "Top")
        ]
        self.activity: str | None = None
        self.carrying: str | None = None
        self.extension = 0.0
        self.pair_offset = 0.0

    @staticmethod
    def _writable(stage: Any, path: str) -> Any:
        """Returns the spec of a fork stage, or None if a replacing file has no such stage."""
        attribute = stage.GetAttributeAtPath(path)
        if not attribute or not attribute.IsValid():
            return None
        # A stage from a referenced file needs an opinion in the root layer to be written to.
        attribute.Set(attribute.Get())
        return stage.GetRootLayer().GetAttributeAtPath(path)


class WarehouseScene:
    def __init__(
        self, stage: Any, description: WarehouseDescription, models: str = "simple"
    ) -> None:
        self.stage = stage
        self.detailed = models == MODELS_DETAILED
        self.layout = create_layout(description.layout)
        self._crane_size = crane_dimensions(self.layout)
        self.bounds = self.layout.bounds()
        appearance.look_warnings.clear()
        UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
        UsdGeom.SetStageMetersPerUnit(stage, 1.0)
        stage.SetDefaultPrim(UsdGeom.Xform.Define(stage, WORLD).GetPrim())

        appearance.create_lights(stage, f"{WORLD}/Dome", f"{WORLD}/Sun")
        appearance.create_floor(stage, f"{WORLD}/Floor", self.bounds)
        self._build_racks()
        self._load_prototypes = self._build_loads()
        self._build_transfer_points(description)
        UsdGeom.Xform.Define(stage, CRANES)
        for aisle in range(1, self.layout.aisle_count + 1):
            appearance.create_crane(
                stage, f"{CRANES}/Aisle_{aisle}", self.layout, self.detailed, self._load_prototypes
            )
            if self.detailed:
                appearance.create_aisle_light(
                    stage, f"{AISLE_LIGHTS}/Aisle_{aisle}", self.layout, aisle
                )
        appearance.create_highlight(stage, SELECTION, self.layout)
        self._build_camera()

        layer = stage.GetRootLayer()
        self._cranes = {
            aisle: _Crane(stage, aisle) for aisle in range(1, self.layout.aisle_count + 1)
        }
        self._poses: dict[int, ForkPose] = {}
        self._invisible_spec = layer.GetAttributeAtPath(f"{LOADS}.invisibleIds")
        self._prototypes_spec = layer.GetAttributeAtPath(f"{LOADS}.protoIndices")
        self._highlight_translate = layer.GetAttributeAtPath(f"{SELECTION}.xformOp:translate")
        self._highlight_visibility = layer.GetAttributeAtPath(f"{SELECTION}.visibility")
        self._prototypes = [0] * self.layout.cell_count
        self._hidden = set(range(self.layout.cell_count))
        self._prototypes_changed = False
        self._written_hidden: list[int] | None = None
        self._lifted: list[int] = []

    def _build_racks(self) -> None:
        layout = self.layout
        instancer = UsdGeom.PointInstancer.Define(self.stage, RACKS)
        upright, beam = appearance.create_rack_prototypes(self.stage, RACKS, layout)
        targets = instancer.CreatePrototypesRel()
        targets.AddTarget(upright)
        targets.AddTarget(beam)
        positions = []
        prototypes = []
        half_width = layout.cell_width / 2
        for aisle in range(1, layout.aisle_count + 1):
            for rack in range(1, layout.racks_per_aisle + 1):
                rack_z = layout.rack_z(aisle, rack)
                for z in (rack_z - half_width, rack_z + half_width):
                    for bay in range(layout.bays + 1):
                        positions.append(Gf.Vec3f(bay * layout.cell_length, layout.height / 2, z))
                        prototypes.append(0)
                    for level in range(layout.levels + 1):
                        positions.append(Gf.Vec3f(layout.length / 2, level * layout.cell_height, z))
                        prototypes.append(1)
        instancer.CreatePositionsAttr(Vt.Vec3fArray(positions))
        instancer.CreateProtoIndicesAttr(Vt.IntArray(prototypes))

    def _build_loads(self) -> list[str]:
        layout = self.layout
        instancer = UsdGeom.PointInstancer.Define(self.stage, LOADS)
        targets = instancer.CreatePrototypesRel()
        prototypes = appearance.create_load_prototypes(self.stage, LOADS, layout)
        for path in prototypes:
            targets.AddTarget(path)
        positions = [Gf.Vec3f(*layout.cell_box(cell).center) for cell in layout.cells()]
        instancer.CreatePositionsAttr(Vt.Vec3fArray(positions))
        instancer.CreateProtoIndicesAttr(Vt.IntArray([0] * layout.cell_count))
        instancer.CreateInvisibleIdsAttr(Vt.Int64Array(list(range(layout.cell_count))))
        return prototypes

    def _build_transfer_points(self, description: WarehouseDescription) -> None:
        layout = self.layout
        UsdGeom.Xform.Define(self.stage, f"{WORLD}/TransferPoints")
        for aisle in range(1, layout.aisle_count + 1):
            ends = description.transfer_points[str(aisle)]
            for end in ENDS:
                roles = [role for role in TRANSFER_ROLES if role in ends[end]]
                for index, role in enumerate(roles):
                    side_by_side = (
                        (index - 0.5) * 0.5 * layout.aisle_width if len(roles) == 2 else 0
                    )
                    appearance.create_transfer_point(
                        self.stage,
                        f"{WORLD}/TransferPoints/Aisle_{aisle}_{end}_{role}",
                        layout,
                        role,
                        (layout.end_x(end), layout.aisle_center_z(aisle) + side_by_side),
                    )

    def _build_camera(self) -> None:
        camera = UsdGeom.Camera.Define(self.stage, CAMERA)
        camera.CreateFocalLengthAttr(FOCAL_LENGTH_MM)
        camera.CreateHorizontalApertureAttr(HORIZONTAL_APERTURE_MM)
        camera.CreateVerticalApertureAttr(VERTICAL_APERTURE_MM)
        camera.AddTransformOp()
        self.show_default_view()

    def show_default_view(self) -> None:
        """Places the camera so that it shows the whole warehouse."""
        low, high = (Gf.Vec3d(*corner) for corner in (self.bounds.min, self.bounds.max))
        center = (low + high) * 0.5
        radius = (high - low).GetLength() / 2
        # Kit fits the horizontal aperture to the viewport, so a wide viewport sees less vertically.
        half_angle = math.atan(
            HORIZONTAL_APERTURE_MM / WIDEST_VIEWPORT_ASPECT / (2 * FOCAL_LENGTH_MM)
        )
        distance = radius / math.sin(half_angle) * 1.02
        eye = center + VIEW_DIRECTION * distance
        camera = UsdGeom.Camera(self.stage.GetPrimAtPath(CAMERA))
        camera.CreateClippingRangeAttr(Gf.Vec2f(max(distance / 500, 0.01), distance * 20))
        view = Gf.Matrix4d().SetLookAt(eye, center, Gf.Vec3d(0.0, 1.0, 0.0))
        self.stage.GetPrimAtPath(CAMERA).GetAttribute("xformOp:transform").Set(view.GetInverse())

    def crane_shape(self, aisle: int, crane: Any) -> list[Box]:
        """Returns the boxes of a detailed crane as it is shown, for selection."""
        pose = self._poses.get(aisle, REST)
        return list(
            crane_boxes(
                self.layout,
                self._crane_size,
                aisle,
                crane.position,
                pose.extension_m,
                pose.pair_offset_m,
                crane.carrying is not None or pose.pair_on_crane,
            ).values()
        )

    def crane_highlight_point(self, aisle: int, position: tuple[float, float]) -> Vector:
        """Returns the center of the outline around a crane or the load that it carries."""
        x, y, z = self.layout.crane_world_position(aisle, position)
        return (x, y + self.layout.cell_height / 2, z) if self.detailed else (x, y, z)

    def set_highlight(self, point: Vector | None) -> None:
        """Marks a 3D point as selected, or removes the mark when given None."""
        with Sdf.ChangeBlock():
            if point is None:
                self._highlight_visibility.default = UsdGeom.Tokens.invisible
            else:
                self._highlight_translate.default = Gf.Vec3d(*point)
                self._highlight_visibility.default = UsdGeom.Tokens.inherited

    def update(self, state: RunState, changes: CellChanges, source: StateSource) -> None:
        """Shows a state, writing only what changed, in one change to the stage."""
        if self.detailed:
            self._poses = {
                aisle: fork_pose(crane.handling, state.time_s, self.layout)
                for aisle, crane in state.cranes.items()
            }
        with Sdf.ChangeBlock():
            self._update_loads(changes, source)
            for aisle, crane in state.cranes.items():
                self._update_crane(aisle, crane, source)

    def _update_loads(self, changes: CellChanges, source: StateSource) -> None:
        layout = self.layout
        if changes.all:
            self._hidden = set(range(layout.cell_count))
            for load in source.stored_load_units():
                instance = layout.cell_instance(load.location)  # type: ignore[arg-type]
                self._hidden.discard(instance)
                self._set_prototype(instance, load.article)
        else:
            for location in changes.cells:
                instance = layout.cell_instance(location)
                load = source.cell(location).load
                if load is None:
                    self._hidden.add(instance)
                else:
                    self._hidden.discard(instance)
                    self._set_prototype(instance, load.article)
        if self._prototypes_changed:
            self._prototypes_spec.default = Vt.IntArray(self._prototypes)
            self._prototypes_changed = False
        # A pair on its way out of a cell shows on the crane, and the recording moves it later.
        lifted = [
            layout.cell_instance(pose.hidden_cell)
            for pose in self._poses.values()
            if pose.hidden_cell is not None
        ]
        if not changes.all and not changes.cells and not lifted and not self._lifted:
            return
        if lifted == self._lifted and not changes.all and not changes.cells:
            return
        self._lifted = lifted
        hidden = sorted(self._hidden.union(lifted))
        if hidden != self._written_hidden:
            self._written_hidden = hidden
            self._invisible_spec.default = Vt.Int64Array(hidden)

    def _set_prototype(self, instance: int, article: int) -> None:
        prototype = appearance.article_prototype(article)
        if self._prototypes[instance] != prototype:
            self._prototypes[instance] = prototype
            self._prototypes_changed = True

    def _update_crane(self, aisle: int, crane: Any, source: StateSource) -> None:
        specs = self._cranes[aisle]
        x, y, z = self.layout.crane_world_position(aisle, crane.position)
        specs.translate.default = Gf.Vec3d(x, 0.0, z)
        specs.carriage.default = Gf.Vec3d(0.0, y, 0.0)
        if crane.activity != specs.activity:
            specs.activity = crane.activity
            colors = Vt.Vec3fArray([appearance.activity_color(crane.activity)])
            for spec in specs.colors:
                spec.default = colors
        if self.detailed:
            self._update_forks(aisle, crane, source)
        elif crane.carrying != specs.carrying:
            specs.carrying = crane.carrying
            carried = None if crane.carrying is None else source.load(crane.carrying)
            if carried is None:
                specs.carried_visibility.default = UsdGeom.Tokens.invisible
            else:
                specs.carried_visibility.default = UsdGeom.Tokens.inherited
                specs.carried_color.default = Vt.Vec3fArray(
                    [appearance.article_color(carried.article)]
                )

    def _update_forks(self, aisle: int, crane: Any, source: StateSource) -> None:
        specs = self._cranes[aisle]
        pose = self._poses[aisle]
        if pose.extension_m != specs.extension:
            specs.extension = pose.extension_m
            middle = Gf.Vec3d(0.0, 0.0, pose.extension_m / 2)
            top = Gf.Vec3d(0.0, 0.0, pose.extension_m)
            for index, spec in enumerate(specs.fork_stages):
                if spec is not None:
                    spec.default = top if index % 2 else middle
        if pose.hidden_cell is not None:
            shown = source.cell(pose.hidden_cell).load
        else:
            shown = None if crane.carrying is None else source.load(crane.carrying)
        key = None if shown is None else shown.key
        if key != specs.carrying:
            specs.carrying = key
            if shown is None:
                specs.carried_visibility.default = UsdGeom.Tokens.invisible
            else:
                specs.carried_visibility.default = UsdGeom.Tokens.inherited
                specs.carried_prototypes.default = Vt.IntArray(
                    [appearance.article_prototype(shown.article)]
                )
        if pose.pair_offset_m != specs.pair_offset:
            specs.pair_offset = pose.pair_offset_m
            specs.carried_positions.default = Vt.Vec3fArray(
                [Gf.Vec3f(0.0, self.layout.cell_height / 2, pose.pair_offset_m)]
            )
