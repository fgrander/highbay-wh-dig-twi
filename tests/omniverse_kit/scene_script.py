"""Runs inside Kit: builds scenes and reports what they contain, for test_kit_scene.py."""

import difflib
from typing import Any

import omni.usd
from kit_test_support import run_script, wait_frames
from pxr import Sdf, UsdGeom

from highbay.replay.core.playback import Playback
from highbay.replay.core.recorded_source import open_recording
from highbay.replay.scene import WarehouseScene

PRIM_PATHS = (
    "/World/Floor",
    "/World/Dome",
    "/World/Sun",
    "/World/Racks",
    "/World/Loads",
    "/World/Cranes/Aisle_1",
    "/World/Cranes/Aisle_1/Carriage",
    "/World/Camera",
    "/World/Selection",
)


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


async def new_stage() -> Any:
    context = omni.usd.get_context()
    await context.new_stage_async()
    return context.get_stage()


def world_text(stage: Any) -> str:
    """Returns the text of the scene. Kit writes its own render settings beside it in the layer."""
    layer = Sdf.Layer.CreateAnonymous(".usda")
    Sdf.CopySpec(stage.GetRootLayer(), "/World", layer, "/World")
    return layer.ExportToString()


def snapshot(stage: Any) -> dict[str, Any]:
    loads = UsdGeom.PointInstancer(stage.GetPrimAtPath("/World/Loads"))
    cranes = {}
    for prim in stage.GetPrimAtPath("/World/Cranes").GetChildren():
        path = prim.GetPath()
        carriage = stage.GetPrimAtPath(path.AppendChild("Carriage"))
        carried = stage.GetPrimAtPath(path.AppendPath("Carriage/CarriedLoad"))
        cranes[prim.GetName()] = {
            "translate": list(prim.GetAttribute("xformOp:translate").Get()),
            "carriage": list(carriage.GetAttribute("xformOp:translate").Get()),
            "color": list(
                stage.GetPrimAtPath(path.AppendChild("Mast"))
                .GetAttribute("primvars:displayColor")
                .Get()[0]
            ),
            "carried_visible": carried.GetAttribute("visibility").Get() != "invisible",
        }
    return {
        "invisible": sorted(int(value) for value in loads.GetInvisibleIdsAttr().Get()),
        "prototypes": [int(value) for value in loads.GetProtoIndicesAttr().Get()],
        "cranes": cranes,
    }


async def play(stage: Any, folder: str, speed: int, step_s: float, end_s: float) -> dict[str, Any]:
    """Plays a span of simulated time at one update rate, with a clock under test's control."""
    source = open_recording(folder)
    scene = WarehouseScene(stage, source.describe())
    clock = FakeClock()
    playback = Playback(source, clock=clock)
    end_s = min(end_s, source.time_range()[1])
    playback.set_speed(speed)
    playback.play()
    while playback.time_s < end_s:
        clock.now += step_s
        playback.update()
        if playback.time_s > end_s:
            playback.move_to(end_s)
        state = source.state_at(playback.time_s)
        scene.update(state, source.take_changes(), source)
    return snapshot(stage)


async def main(arguments: dict[str, Any]) -> dict[str, Any]:
    folder = arguments["run_folder"]
    results: dict[str, Any] = {}

    source = open_recording(folder)
    stage = await new_stage()
    scene = WarehouseScene(stage, source.describe())
    first_text = world_text(stage)

    results["up_axis"] = UsdGeom.GetStageUpAxis(stage)
    results["meters_per_unit"] = UsdGeom.GetStageMetersPerUnit(stage)
    results["prims"] = {path: stage.GetPrimAtPath(path).GetTypeName() for path in PRIM_PATHS}
    results["transfer_points"] = [
        prim.GetName() for prim in stage.GetPrimAtPath("/World/TransferPoints").GetChildren()
    ]
    loads = UsdGeom.PointInstancer(stage.GetPrimAtPath("/World/Loads"))
    results["load_instances"] = len(loads.GetPositionsAttr().Get())
    results["load_prototypes"] = len(loads.GetPrototypesRel().GetTargets())
    results["first_load_position"] = list(loads.GetPositionsAttr().Get()[0])
    results["rack_instances"] = len(
        UsdGeom.PointInstancer(stage.GetPrimAtPath("/World/Racks")).GetPositionsAttr().Get()
    )

    scene.update(source.state_at(0.0), source.take_changes(), source)
    results["start"] = snapshot(stage)
    forward = []
    for time_s in arguments["times"]:
        scene.update(source.state_at(time_s), source.take_changes(), source)
        forward.append(snapshot(stage))
    results["forward"] = forward
    backward = []
    for time_s in reversed(arguments["times"]):
        scene.update(source.state_at(time_s), source.take_changes(), source)
        backward.append(snapshot(stage))
    results["backward"] = list(reversed(backward))
    await wait_frames(5)

    second = await new_stage()
    WarehouseScene(second, open_recording(folder).describe())
    second_text = world_text(second)
    results["same_text"] = first_text == second_text
    results["text_diff"] = list(
        difflib.unified_diff(first_text.splitlines(), second_text.splitlines(), lineterm="", n=0)
    )[:60]

    empty = await new_stage()
    results["empty"] = await play(empty, arguments["empty_folder"], 3600, 1.0, 10_000_000.0)

    end_s = arguments["play_end_s"]
    results["rate_slow"] = await play(await new_stage(), folder, 60, 1 / 5, end_s)
    results["rate_fast"] = await play(await new_stage(), folder, 60, 1 / 60, end_s)
    results["many_per_frame"] = await play(await new_stage(), folder, 3600, 1.0, end_s)
    return results


run_script(main)
