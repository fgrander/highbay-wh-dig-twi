"""Runs inside Kit: connects a scripted source and a replaced look, for test_kit_state_source.py."""

import sys
from typing import Any

import omni.usd
from kit_test_support import run_script, wait_frames
from pxr import UsdGeom

from highbay.replay.extension import get_controller


def snapshot(controller: Any) -> dict[str, Any]:
    stage = omni.usd.get_context().get_stage()
    loads = UsdGeom.PointInstancer(stage.GetPrimAtPath("/World/Loads"))
    return {
        "time_s": controller.playback.time_s,
        "playing": controller.playback.playing,
        "crane_x": stage.GetPrimAtPath("/World/Cranes/Aisle_1")
        .GetAttribute("xformOp:translate")
        .Get()[0],
        "hidden": len(loads.GetInvisibleIdsAttr().Get()),
        "figures": controller.window.figures_text,
        "message": controller.message,
    }


async def main(arguments: dict[str, Any]) -> dict[str, Any]:
    sys.path.insert(0, arguments["data_directory"])
    from scripted_state_source import ScriptedSource

    await wait_frames(5)
    controller = get_controller()
    source = ScriptedSource(end_s=10.0)
    controller.open_source(source)
    await wait_frames(3)
    results: dict[str, Any] = {
        "start": snapshot(controller),
        "controls": controller.window.control_states(),
        "identification": controller.window.identification_text,
    }

    controller.set_speed(3600)
    controller.toggle_playing()
    await wait_frames(30)
    results["held"] = snapshot(controller)

    source.grow(20.0)
    await wait_frames(30)
    results["continued"] = snapshot(controller)

    # The load unit leaves its cell as time passes, through the interface's changes alone.
    source.grow(50.0)
    await wait_frames(30)
    results["load_left"] = snapshot(controller)

    controller.window.show_message("")
    controller.go_to_highest_backlog()
    await wait_frames(2)
    results["no_jump"] = controller.playback.playing
    return results


run_script(main)
