"""Runs inside Kit: opens runs with detailed cranes, and reports them, for test_kit_crane.py."""

from typing import Any

import omni.usd
from kit_test_support import run_script, wait_frames
from pxr import Sdf, Usd, UsdGeom, UsdShade

from highbay.replay import appearance
from highbay.replay.core.crane_dimensions import crane_boxes, crane_dimensions
from highbay.replay.extension import get_controller

CRANE = "/World/Cranes/Aisle_1"
MAST = f"{CRANE}/Mast"
PLATFORM = f"{CRANE}/Carriage/Platform"
# Each box for selection, and the parts of the model that it has to cover.
PARTS = {
    "ColumnLeft": [f"{MAST}/ColumnLeft"],
    "ColumnRight": [f"{MAST}/ColumnRight"],
    "RailLeft": [f"{MAST}/RailLeftFront", f"{MAST}/RailLeftBack"],
    "RailRight": [f"{MAST}/RailRightFront", f"{MAST}/RailRightBack"],
    "TravelGearLeft": [f"{MAST}/BogieLeft", f"{MAST}/BogieStripeLeft", f"{MAST}/WheelLeftFront1"],
    "TravelGearRight": [
        f"{MAST}/BogieRight",
        f"{MAST}/BogieStripeRight",
        f"{MAST}/WheelRightBack2",
    ],
    "TopBeam": [f"{MAST}/TopBeam", f"{MAST}/TopRollerLeftFront", f"{MAST}/TopRollerRightBack"],
    "FloorTie": [f"{MAST}/FloorTie"],
    "Cabinet": [f"{MAST}/Cabinet"],
    "Ladder": [f"{MAST}/LadderA", f"{MAST}/LadderB"],
    "EndFrameLeft": [
        f"{PLATFORM}/EndFrameLeft",
        f"{PLATFORM}/RollerLeftFrontLow",
    ],
    "EndFrameRight": [
        f"{PLATFORM}/EndFrameRight",
        f"{PLATFORM}/RollerRightBackHigh",
    ],
    "Plate": [f"{PLATFORM}/Plate"],
    "Section1": [f"{PLATFORM}/Section1"],
    "Section2": [f"{PLATFORM}/Section2"],
}


def part_bounds(stage: Any, paths: list[str]) -> dict[str, list[float]]:
    cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_])
    bounds = None
    for path in paths:
        box = cache.ComputeWorldBound(stage.GetPrimAtPath(path)).ComputeAlignedRange()
        if bounds is None:
            bounds = box
        else:
            bounds.UnionWith(box)
    return {"min": list(bounds.GetMin()), "max": list(bounds.GetMax())}


def world_bounds_of_boxes(boxes: dict[str, Any]) -> dict[str, dict[str, list[float]]]:
    return {
        name: {
            "min": [c - s / 2 for c, s in zip(box.center, box.size, strict=True)],
            "max": [c + s / 2 for c, s in zip(box.center, box.size, strict=True)],
        }
        for name, box in boxes.items()
    }


def world_subtree(stage: Any) -> str:
    layer = Sdf.Layer.CreateAnonymous(".usda")
    Sdf.CreatePrimInLayer(layer, "/World")
    Sdf.CopySpec(stage.GetRootLayer(), "/World", layer, "/World")
    return layer.ExportToString()


async def main(arguments: dict[str, Any]) -> dict[str, Any]:
    await wait_frames(5)
    controller = get_controller()
    results: dict[str, Any] = {"runs": {}}

    for label, folder in arguments["run_folders"].items():
        assert controller.open_run_folder(folder), controller.message
        await wait_frames(2)
        stage = omni.usd.get_context().get_stage()
        positions = {}
        for time_s in arguments["times"]:
            controller.move_to(time_s)
            await wait_frames(1)
            crane = stage.GetPrimAtPath(CRANE).GetAttribute("xformOp:translate").Get()
            lift = stage.GetPrimAtPath(f"{CRANE}/Carriage").GetAttribute("xformOp:translate").Get()
            positions[str(time_s)] = [crane[0], lift[1]]
        results["runs"][label] = positions

    # The event-driven run, at its start, for the remaining checks.
    folder = arguments["run_folders"]["event"]
    assert controller.open_run_folder(folder)
    await wait_frames(2)
    stage = omni.usd.get_context().get_stage()
    first = world_subtree(stage)
    results["root_layer_has_temporary_layer"] = "anon:" in stage.GetRootLayer().ExportToString()
    assert controller.open_run_folder(folder)
    await wait_frames(2)
    stage = omni.usd.get_context().get_stage()
    results["two_builds_identical"] = first == world_subtree(stage)

    scene = controller.scene
    layout = scene.layout
    size = crane_dimensions(layout)
    results["size"] = {"height": size.height, "column_x": size.column_x}
    results["aisle_count"] = layout.aisle_count
    results["lights"] = [
        stage.GetPrimAtPath(f"/World/AisleLights/Aisle_{aisle}").GetTypeName()
        for aisle in range(1, layout.aisle_count + 1)
    ]

    # Materials arrive with the copy, at their new paths.
    binding = UsdShade.MaterialBindingAPI(stage.GetPrimAtPath(f"{MAST}/BogieLeft"))
    results["bogie_material"] = str(binding.ComputeBoundMaterial()[0].GetPath())
    binding = UsdShade.MaterialBindingAPI(stage.GetPrimAtPath(f"{PLATFORM}/Section1/Top/TineA"))
    results["fork_material"] = str(binding.ComputeBoundMaterial()[0].GetPath())

    # A moment with the crane away from the warehouse's start, raised, and holding nothing.
    time_s = arguments["raised_time"]
    controller.move_to(time_s)
    await wait_frames(2)
    state = controller.source.state_at(time_s)
    position = state.cranes[1].position
    results["position"] = list(position)
    expected = crane_boxes(layout, size, 1, position)
    results["boxes"] = {
        name: box for name, box in world_bounds_of_boxes(expected).items() if name in PARTS
    }
    results["bounds"] = {name: part_bounds(stage, paths) for name, paths in PARTS.items()}

    # Clicks at visible points of each part.
    clicks = {}
    for name, box in expected.items():
        for share in (-0.3, 0.3):
            point = [
                box.center[0] + share * box.size[0],
                box.center[1] + share * box.size[1],
            ]
            controller.select(None)
            controller.select_along_ray((point[0], point[1], -1000.0), (0.0, 0.0, 1.0))
            selection = controller.selection
            clicks[f"{name} {share}"] = (
                None
                if selection is None
                else [
                    selection.kind,
                    selection.aisle,
                ]
            )
    results["clicks"] = clicks

    # The outline of a selected crane surrounds its load space.
    controller.select_along_ray(
        (expected["ColumnLeft"].center[0], position[1] + 0.05, -1000.0), (0.0, 0.0, 1.0)
    )
    await wait_frames(1)
    results["outline"] = list(
        stage.GetPrimAtPath("/World/Selection").GetAttribute("xformOp:translate").Get()
    )
    results["cell_height"] = layout.cell_height
    results["crane_z"] = layout.aisle_center_z(1)

    # Colors, on parts of both the mast and the carriage, for each activity.
    colors = {}
    for activity, time_s in arguments["activity_times"].items():
        controller.move_to(time_s)
        await wait_frames(1)
        seen = []
        for path in (f"{MAST}/ColumnLeft", f"{PLATFORM}/EndFrameRight"):
            primvar = UsdGeom.PrimvarsAPI(stage.GetPrimAtPath(path)).FindPrimvarWithInheritance(
                "displayColor"
            )
            seen.append(list(primvar.Get()[0]))
        colors[activity] = seen
    results["colors"] = colors
    results["warnings"] = appearance.look_warnings
    results["message"] = controller.message
    return results


run_script(main)
