"""Runs inside Kit. Gives a test script its arguments, and writes its results or its failure."""

import asyncio
import json
import os
import traceback
from collections.abc import Awaitable, Callable
from typing import Any

import omni.kit.app

_running: list[asyncio.Future[None]] = []


async def wait_frames(count: int) -> None:
    app = omni.kit.app.get_app()
    for _ in range(count):
        await app.next_update_async()


def run_script(main: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]) -> None:
    """Runs `main` and ends Kit with `os._exit`, as a request to quit does not end it."""
    with open(os.environ["HIGHBAY_KIT_ARGUMENTS"], encoding="utf-8") as file:
        arguments = json.load(file)

    async def run() -> None:
        try:
            results = await main(arguments)
        except BaseException:
            results = {"script_error": traceback.format_exc()}
        temporary = arguments["results_file"] + ".part"
        with open(temporary, "w", encoding="utf-8") as file:
            json.dump(results, file)
        os.replace(temporary, arguments["results_file"])
        os._exit(0)

    _running.append(asyncio.ensure_future(run()))
