"""Runs inside Kit: moves through handling steps, and reports forks, for test_kit_forks.py."""

import sys
from typing import Any

import omni.usd
from kit_test_support import run_script, wait_frames
from pxr import UsdGeom

from highbay.replay.extension import get_controller
from highbay.replay.scene import LOADS

PLATFORM = "Carriage/Platform"


def snapshot(stage: Any, controller: Any, aisle: int) -> dict[str, Any]:
    crane = f"/World/Cranes/Aisle_{aisle}"
    stages = {}
    for section in ("Section1", "Section2"):
        for name in ("Middle", "Top"):
            attribute = stage.GetAttributeAtPath(
                f"{crane}/{PLATFORM}/{section}/{name}.xformOp:translate"
            )
            stages[f"{section}/{name}"] = list(attribute.Get())
    carried = stage.GetPrimAtPath(f"{crane}/Carriage/CarriedLoad")
    instancer = UsdGeom.PointInstancer(stage.GetPrimAtPath(LOADS))
    return {
        "stages": stages,
        "carried_visible": carried.GetAttribute("visibility").Get() != "invisible",
        "carried_position": list(carried.GetAttribute("positions").Get()[0]),
        "carried_prototype": carried.GetAttribute("protoIndices").Get()[0],
        "hidden": sorted(instancer.GetInvisibleIdsAttr().Get()),
    }


async def main(arguments: dict[str, Any]) -> dict[str, Any]:
    await wait_frames(5)
    controller = get_controller()
    assert controller.open_run_folder(arguments["run_folder"]), controller.message
    await wait_frames(2)
    stage = omni.usd.get_context().get_stage()
    results: dict[str, Any] = {"steps": []}

    for step in arguments["steps"]:
        aisle = step["aisle"]
        forward = {}
        for time_s in step["times"]:
            controller.move_to(time_s)
            await wait_frames(1)
            forward[str(time_s)] = snapshot(stage, controller, aisle)
        backward = {}
        controller.move_to(step["after"])
        await wait_frames(1)
        for time_s in reversed(step["times"]):
            controller.move_to(time_s)
            await wait_frames(1)
            backward[str(time_s)] = snapshot(stage, controller, aisle)

        # A click from above, on the forks at their furthest.
        controller.move_to(step["middle"])
        await wait_frames(1)
        controller.select(None)
        origin = (step["fork_click"][0], 1000.0, step["fork_click"][1])
        controller.select_along_ray(origin, (0.0, -1.0, 0.0))
        selection = controller.selection
        results["steps"].append(
            {
                **step,
                "forward": forward,
                "backward": backward,
                "clicked": None if selection is None else [selection.kind, selection.aisle],
            }
        )

    if "scripted_data" in arguments:
        sys.path.insert(0, arguments["scripted_data"])
        from scripted_state_source import ScriptedSource

        controller.open_source(ScriptedSource())
        await wait_frames(2)
        stage = omni.usd.get_context().get_stage()
        controller.move_to(5.0)
        await wait_frames(2)
        results["scripted"] = snapshot(stage, controller, 1)
    results["message"] = controller.message
    return results


run_script(main)
