"""Runs inside Kit: opens a run with load definitions, and reports them, for test_kit_loads.py."""

from typing import Any

import omni.usd
from kit_test_support import run_script, wait_frames
from pxr import Usd, UsdGeom, UsdShade

from highbay.replay.extension import get_controller
from highbay.replay.scene import LOADS


def bounds(stage: Any, path: str) -> dict[str, list[float]]:
    cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_])
    box = cache.ComputeLocalBound(stage.GetPrimAtPath(path)).ComputeAlignedRange()
    child_range = {"min": list(box.GetMin()), "max": list(box.GetMax())}
    return child_range


async def main(arguments: dict[str, Any]) -> dict[str, Any]:
    await wait_frames(5)
    controller = get_controller()
    assert controller.open_run_folder(arguments["run_folder"]), controller.message
    await wait_frames(2)
    stage = omni.usd.get_context().get_stage()
    instancer = UsdGeom.PointInstancer(stage.GetPrimAtPath(LOADS))
    scene = controller.scene
    results: dict[str, Any] = {
        "message": controller.message,
        "warnings": controller.window.warnings_text,
        "instance_count": len(instancer.GetPositionsAttr().Get()),
        "cell_count": scene.layout.cell_count,
        "prototype_count": len(instancer.GetPrototypesRel().GetTargets()),
    }

    prototypes = {}
    for index, target in enumerate(instancer.GetPrototypesRel().GetTargets()):
        path = str(target)
        children = {}
        for child in stage.GetPrimAtPath(path).GetChildren():
            children[child.GetName()] = {
                "type": child.GetTypeName(),
                "bounds": bounds(stage, str(child.GetPath())),
            }
        prototypes[str(index)] = {
            "bounds": bounds(stage, path),
            "children": children,
            "has_reference": any(
                child.HasAuthoredReferences() for child in stage.GetPrimAtPath(path).GetChildren()
            ),
        }
    results["prototypes"] = prototypes

    binding = None
    for prim in Usd.PrimRange(stage.GetPrimAtPath(LOADS)):
        if prim.GetName() == "LightBands":
            binding = str(UsdShade.MaterialBindingAPI(prim).GetDirectBinding().GetMaterialPath())
            break
    results["sheet_material"] = binding

    # Stored loads at each sampled time, and details on each.
    results["stored"] = {}
    for time_s in arguments["times"]:
        controller.move_to(time_s)
        await wait_frames(1)
        hidden = set(instancer.GetInvisibleIdsAttr().Get())
        indices = instancer.GetProtoIndicesAttr().Get()
        results["stored"][str(time_s)] = {
            str(instance): int(indices[instance])
            for instance in range(len(indices))
            if instance not in hidden
        }

    # What a crane shows while it carries a load.
    results["carried"] = []
    for entry in arguments["carried"]:
        controller.move_to(entry["time"])
        await wait_frames(1)
        carried = stage.GetPrimAtPath(f"/World/Cranes/Aisle_{entry['aisle']}/Carriage/CarriedLoad")
        controller.select(None)
        results["carried"].append(
            {
                **entry,
                "visible": carried.GetAttribute("visibility").Get() != "invisible",
                "prototype": int(carried.GetAttribute("protoIndices").Get()[0]),
                "targets": [
                    str(path) for path in carried.GetRelationship("prototypes").GetTargets()
                ],
            }
        )

    # Details of a stored load.
    details = {}
    for entry in arguments["details"]:
        controller.move_to(entry["time"])
        await wait_frames(1)
        from highbay.replay.core.picking import Selection

        controller.select(Selection("load", key=entry["key"]))
        await wait_frames(1)
        details[entry["key"]] = controller.window.details_text
    results["details"] = details
    return results


run_script(main)
