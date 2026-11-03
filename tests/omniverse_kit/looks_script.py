"""Runs inside Kit: builds a scene with replaced looks, for test_kit_looks.py."""

from typing import Any

import omni.usd
from kit_test_support import run_script, wait_frames

from highbay.replay import appearance
from highbay.replay.extension import get_controller


async def main(arguments: dict[str, Any]) -> dict[str, Any]:
    await wait_frames(5)
    controller = get_controller()
    assert controller.open_run_folder(arguments["run_folder"])
    await wait_frames(2)
    stage = omni.usd.get_context().get_stage()
    mast = stage.GetPrimAtPath("/World/Cranes/Aisle_1/Mast")
    ball = stage.GetPrimAtPath("/World/Cranes/Aisle_1/Mast/Ball")
    beam = stage.GetPrimAtPath("/World/Racks/Beam")
    positions = {}
    colors = {}
    for time_s in arguments["times"]:
        controller.move_to(time_s)
        await wait_frames(2)
        crane = stage.GetPrimAtPath("/World/Cranes/Aisle_1")
        positions[str(time_s)] = list(crane.GetAttribute("xformOp:translate").Get())
        colors[str(time_s)] = list(mast.GetAttribute("primvars:displayColor").Get()[0])
    return {
        "mast_type": mast.GetTypeName(),
        "mast_has_reference": mast.HasAuthoredReferences(),
        "mast_child": ball.GetTypeName() if ball else None,
        "mast_translate": list(mast.GetAttribute("xformOp:translate").Get()),
        "beam_type": beam.GetTypeName(),
        "warnings": appearance.look_warnings,
        "positions": positions,
        "colors": colors,
        "message": controller.message,
    }


run_script(main)
