"""Runs inside Kit: opens unusable and usable run folders, for test_kit_errors.py."""

from typing import Any

import omni.usd
from kit_test_support import run_script, wait_frames

from highbay.replay.extension import get_controller


def has_scene() -> bool:
    return omni.usd.get_context().get_stage().GetPrimAtPath("/World/Loads").IsValid()


async def main(arguments: dict[str, Any]) -> dict[str, Any]:
    await wait_frames(5)
    controller = get_controller()
    results: dict[str, Any] = {}

    # With no run open, a bad folder leaves no scene behind.
    for name, folder in arguments["bad_folders"].items():
        controller.open_run_folder(folder)
        await wait_frames(2)
        results[name] = {"message": controller.message, "has_scene": has_scene()}

    # A good folder opens paused at time 0, and clears the message.
    controller.open_run_folder(arguments["good_folder"])
    await wait_frames(2)
    controller.playback.move_to(arguments["later_s"])
    await wait_frames(2)
    results["opened"] = {
        "message": controller.message,
        "has_scene": has_scene(),
        "time_s": controller.playback.time_s,
        "seed": controller.source.describe().run["seed"],
    }

    # A bad folder leaves an open run open and unchanged.
    first_source = controller.source
    controller.open_run_folder(arguments["bad_folders"]["unsupported"])
    await wait_frames(2)
    results["kept"] = {
        "message": controller.message,
        "same_source": controller.source is first_source,
        "time_s": controller.playback.time_s,
        "has_scene": has_scene(),
    }

    # A second good folder replaces it, paused at time 0.
    controller.open_run_folder(arguments["other_folder"])
    await wait_frames(2)
    results["replaced"] = {
        "message": controller.message,
        "same_source": controller.source is first_source,
        "time_s": controller.playback.time_s,
        "playing": controller.playback.playing,
        "aisles": controller.source.describe().layout["aisle_count"],
    }
    return results


run_script(main)
