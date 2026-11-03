"""Runs inside Kit: measures opening, frame rate, and moving to a time."""

import random
import time
from typing import Any

import omni.kit.app
from kit_test_support import run_script, wait_frames
from omni.kit.viewport.utility import get_active_viewport

from highbay.replay.extension import get_controller

WARM_UP_S = 45.0
MEASURE_S = 20.0
SPEED = 600
MOVES = 20


async def frames_per_second(seconds: float) -> dict[str, float]:
    app = omni.kit.app.get_app()
    started = time.perf_counter()
    last = started
    slowest = 0.0
    frames = 0
    while time.perf_counter() - started < seconds:
        await app.next_update_async()
        now = time.perf_counter()
        slowest = max(slowest, now - last)
        last = now
        frames += 1
    return {"fps": frames / (last - started), "slowest_frame_s": slowest}


async def main(arguments: dict[str, Any]) -> dict[str, Any]:
    await wait_frames(5)
    controller = get_controller()
    viewport = get_active_viewport()

    started = time.perf_counter()
    assert controller.open_run_folder(arguments["run_folder"]), controller.message
    results: dict[str, Any] = {
        "open_s": time.perf_counter() - started,
        "warnings": controller.window.warnings_text,
    }

    # By default the viewport follows its frame's size, which would make the measurement too kind.
    viewport.fill_frame = False
    viewport.resolution = (1920, 1080)

    # Shaders and the scene's first frames are not what the frame rate is about.
    await frames_per_second(WARM_UP_S)
    results["resolution"] = list(viewport.resolution)
    results["camera"] = str(viewport.camera_path)

    controller.set_speed(SPEED)
    controller.toggle_playing()
    results["playing"] = await frames_per_second(MEASURE_S)
    results["played_to_s"] = controller.playback.time_s
    controller.toggle_playing()

    generator = random.Random(1)
    duration = controller.source.time_range()[1]
    moves = []
    for _ in range(MOVES):
        target = generator.uniform(0.0, duration)
        started = time.perf_counter()
        controller.move_to(target)
        await wait_frames(1)
        moves.append(time.perf_counter() - started)
        assert controller.playback.time_s == target
    results["moves_s"] = moves
    return results


run_script(main)
