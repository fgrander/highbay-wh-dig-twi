"""Runs inside Kit: reads what the window and scene show, for test_kit_panels.py."""

from typing import Any

import carb.settings
from kit_test_support import run_script, wait_frames
from omni.kit.viewport.utility import get_active_viewport
from pxr import Gf

from highbay.replay.extension import get_controller
from highbay.replay.viewport_click import ray_at

KIT_SELECTION_SETTING = "/exts/omni.kit.viewport.window/startup/selectionManipulator/enabled"


def crane_color(controller: Any, aisle: int) -> list[float]:
    prim = controller.scene.stage.GetPrimAtPath(f"/World/Cranes/Aisle_{aisle}/Mast")
    return list(prim.GetAttribute("primvars:displayColor").Get()[0])


async def main(arguments: dict[str, Any]) -> dict[str, Any]:
    await wait_frames(5)
    controller = get_controller()
    assert controller.open_run_folder(arguments["run_folder"])
    await wait_frames(2)
    results: dict[str, Any] = {"at_times": []}
    for time_s in arguments["times"]:
        controller.move_to(time_s)
        await wait_frames(2)
        results["at_times"].append(
            {
                "figures": controller.window.figures_text,
                "colors": {
                    str(aisle): crane_color(controller, aisle)
                    for aisle in controller.source.state_at(time_s).cranes
                },
            }
        )
    results["identification"] = controller.window.identification_text
    results["kit_selection"] = carb.settings.get_settings().get(KIT_SELECTION_SETTING)
    results["legend"] = controller.window.legend_labels

    controller.toggle_playing()
    await wait_frames(2)
    controller.go_to_highest_backlog()
    await wait_frames(2)
    results["peak"] = {
        "time_s": controller.playback.time_s,
        "playing": controller.playback.playing,
        "figures": controller.window.figures_text,
    }

    # Selection: a ray straight down the mast of crane 1, and details for each kind.
    state = controller.source.state_at(controller.playback.time_s)
    x = state.cranes[1].position[0]
    z = controller.scene.layout.aisle_center_z(1)
    controller.select_along_ray((x, 0.5, z - 1000.0), (0.0, 0.0, 1.0))
    await wait_frames(2)
    results["crane_selected"] = {
        "details": controller.window.details_text,
        "highlight": highlight(controller),
    }
    # A click at the place on the screen where the mast of crane 1 appears.
    controller.select(None)
    api = (
        get_active_viewport().viewport_api
        if hasattr(get_active_viewport(), "viewport_api")
        else get_active_viewport()
    )
    mast = Gf.Vec3d(x, controller.scene.layout.height / 2, z)
    ndc = api.world_to_ndc.Transform(mast)
    controller.select_along_ray(*ray_at(api, ndc[0], ndc[1]))
    await wait_frames(2)
    results["clicked"] = {"details": controller.window.details_text}
    controller.select_along_ray((x, 1000.0, z), (1.0, 1.0, 1.0))
    await wait_frames(2)
    results["nothing_selected"] = {
        "details": controller.window.details_text,
        "highlight": highlight(controller),
    }
    return results


def highlight(controller: Any) -> dict[str, Any]:
    prim = controller.scene.stage.GetPrimAtPath("/World/Selection")
    return {
        "visibility": prim.GetAttribute("visibility").Get(),
        "translate": list(prim.GetAttribute("xformOp:translate").Get()),
    }


run_script(main)
