"""Connects the replay's parts inside Kit.

Everything but `open_run_folder` works through the state interface alone, so a different source can
be connected with `open_source`. See contracts/state-interface.md.
"""

import asyncio
from typing import Any

import carb
import carb.settings
import omni.ext
import omni.kit.app
import omni.usd
from omni.kit.viewport.utility import get_active_viewport

from .core.playback import Playback
from .core.recorded_source import open_recording
from .core.state_source import StateSource, StateSourceError
from .scene import CAMERA, WarehouseScene
from .window import ReplayWindow

RUN_FOLDER_SETTING = "/exts/highbay.replay/run_folder"
FRAMES_BEFORE_FIRST_RUN = 10

_controller: "ReplayController | None" = None


def get_controller() -> "ReplayController":
    """Returns the running replay, for tests and other extensions."""
    if _controller is None:
        raise RuntimeError("The Highbay Replay extension is not running.")
    return _controller


class ReplayController:
    def __init__(self) -> None:
        self.source: StateSource | None = None
        self.playback: Playback | None = None
        self.scene: WarehouseScene | None = None
        self.message = ""
        self._shown_time_s: float | None = None
        self._shown_playing = False
        self.window = ReplayWindow(self)
        self._update_subscription = (
            omni.kit.app.get_app()
            .get_update_event_stream()
            .create_subscription_to_pop(self._on_update, name="highbay.replay")
        )

    def shutdown(self) -> None:
        self._update_subscription = None
        self.window.window.destroy()

    def _show_message(self, message: str) -> None:
        self.message = message
        self.window.show_message(message)
        if message:
            carb.log_error(message)

    def open_run_folder(self, folder: str) -> bool:
        """Opens a run, or shows why not and leaves any open run as it is."""
        try:
            source = open_recording(folder)
        except StateSourceError as error:
            self._show_message(str(error))
            return False
        self.open_source(source, folder)
        return True

    def open_source(self, source: StateSource, folder: str | None = None) -> None:
        """Replaces any open run with a source, paused at its start."""
        description = source.describe()
        context = omni.usd.get_context()
        context.new_stage()
        self.scene = WarehouseScene(context.get_stage(), description)
        self.source = source
        self.playback = Playback(source)
        self._shown_time_s = None
        viewport = get_active_viewport()
        if viewport is not None:
            viewport.camera_path = CAMERA
        self._show_message("")
        self.window.set_run_controls(True, source.can_move_backward)
        self.window.show_run(folder, source.time_range())
        self._show_state()

    def _on_update(self, _event: Any) -> None:
        if self.playback is None:
            return
        self.playback.update()
        if self.playback.playing != self._shown_playing:
            self._shown_playing = self.playback.playing
            self.window.show_playing(self._shown_playing)
        if self.playback.time_s != self._shown_time_s:
            self._show_state()

    def _show_state(self) -> None:
        if self.source is None or self.playback is None or self.scene is None:
            return
        time_s = self.playback.time_s
        try:
            state = self.source.state_at(time_s)
            changes = self.source.take_changes()
            time_range = self.source.time_range()
        except StateSourceError as error:
            self.playback.pause()
            self._show_message(str(error))
            return
        self.scene.update(state, changes, self.source)
        self.window.show_time_range(time_range)
        self.window.show_state(state, time_range[1])
        self._shown_time_s = time_s

    def toggle_playing(self) -> None:
        if self.playback is None:
            return
        if self.playback.playing:
            self.playback.pause()
        else:
            self.playback.play()

    def restart(self) -> None:
        if self.playback is not None:
            self.playback.restart()

    def move_to(self, time_s: float) -> None:
        if self.playback is not None:
            self.playback.move_to(time_s)

    def set_speed(self, speed: int) -> None:
        if self.playback is not None:
            self.playback.set_speed(speed)

    def default_view(self) -> None:
        if self.scene is not None:
            self.scene.show_default_view()


async def _open_first_run(controller: ReplayController, folder: str) -> None:
    app = omni.kit.app.get_app()
    for _ in range(FRAMES_BEFORE_FIRST_RUN):
        await app.next_update_async()
    controller.open_run_folder(folder)


class HighbayReplayExtension(omni.ext.IExt):
    def on_startup(self, ext_id: str) -> None:
        global _controller
        _controller = ReplayController()
        folder = carb.settings.get_settings().get(RUN_FOLDER_SETTING)
        if folder:
            self._first_run = asyncio.ensure_future(_open_first_run(_controller, folder))

    def on_shutdown(self) -> None:
        global _controller
        if _controller is not None:
            _controller.shutdown()
            _controller = None
