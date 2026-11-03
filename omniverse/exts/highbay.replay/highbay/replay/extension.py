"""Connects the replay's parts inside Kit.

Everything but `open_run_folder` works through the state interface alone, so a different source can
be connected with `open_source`. See contracts/state-interface.md.
"""

import asyncio
from pathlib import Path
from typing import Any

import carb
import carb.settings
import omni.ext
import omni.kit.app
import omni.usd
from omni.kit.viewport.utility import get_active_viewport

from . import appearance
from .core.display_text import cell_details, crane_details, load_details
from .core.layout import Vector
from .core.load_definitions import read_load_definitions
from .core.picking import Selection, select_at
from .core.playback import Playback
from .core.recorded_source import open_recording
from .core.state_source import RunState, StateSource, StateSourceError
from .scene import CAMERA, MODELS_DETAILED, WarehouseScene
from .viewport_click import ViewportClick
from .window import ReplayWindow

RUN_FOLDER_SETTING = "/exts/highbay.replay/run_folder"
MODELS_SETTING = "/exts/highbay.replay/models"
LOAD_DEFINITIONS_SETTING = "/exts/highbay.replay/load_definitions"
DEFAULT_LOAD_DEFINITIONS = Path(__file__).parents[2] / "data" / "load_definitions.toml"
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
        self.selection: Selection | None = None
        self._shown_time_s: float | None = None
        self._shown_playing = False
        self._viewport_click: ViewportClick | None = None
        self.window = ReplayWindow(self)
        self._update_subscription = (
            omni.kit.app.get_app()
            .get_update_event_stream()
            .create_subscription_to_pop(self._on_update, name="highbay.replay")
        )

    def shutdown(self) -> None:
        self._update_subscription = None
        self._viewport_click = None
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
        settings = carb.settings.get_settings()
        models = settings.get(MODELS_SETTING) or MODELS_DETAILED
        # Read at each opening, so that a change shows when a run is opened again.
        definitions = None
        if models == MODELS_DETAILED:
            definitions = read_load_definitions(
                settings.get(LOAD_DEFINITIONS_SETTING) or DEFAULT_LOAD_DEFINITIONS
            )
        self.scene = WarehouseScene(context.get_stage(), description, models, definitions)
        self.source = source
        self.playback = Playback(source)
        self.selection = None
        self._shown_time_s = None
        viewport = get_active_viewport()
        if viewport is not None:
            viewport.camera_path = CAMERA
        self._show_message("")
        self.window.set_run_controls(
            True, source.can_move_backward, description.reported is not None
        )
        self.window.show_run(folder, description)
        self.window.show_warnings(list(appearance.look_warnings))
        self._viewport_click = ViewportClick(self.select_along_ray)
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
        self._show_selection(state)

    def _show_selection(self, state: RunState) -> None:
        if self.source is None or self.scene is None:
            return
        selection = self.selection
        is_load = selection is not None and selection.kind == "load"
        if is_load and self.source.load(selection.key) is None:  # type: ignore[arg-type,union-attr]
            self.selection = None
        self.scene.set_highlight(self._selection_point(state))
        self.window.show_details(self._selection_details(state), self._carried_load(state))

    def _selection_point(self, state: RunState) -> Vector | None:
        selection = self.selection
        if selection is None or self.scene is None or self.source is None:
            return None
        layout = self.scene.layout
        if selection.kind == "crane":
            return self.scene.crane_highlight_point(
                selection.aisle, state.cranes[selection.aisle].position
            )
        if selection.kind == "cell":
            return layout.cell_box(selection.location).center
        load = self.source.load(selection.key)
        if load is None:
            return None
        if load.location is not None:
            return layout.cell_box(load.location).center
        return self.scene.crane_highlight_point(load.crane, state.cranes[load.crane].position)

    def _selection_details(self, state: RunState) -> list[str]:
        selection = self.selection
        if selection is None or self.source is None or self.scene is None:
            return []
        if selection.kind == "crane":
            return crane_details(self.source, state, selection.aisle, self.scene.load_description)
        if selection.kind == "cell":
            return cell_details(self.source, selection.location)
        return load_details(self.source, selection.key, self.scene.load_description)

    def _carried_load(self, state: RunState) -> str | None:
        if self.selection is None or self.selection.kind != "crane":
            return None
        return state.cranes[self.selection.aisle].carrying

    def select(self, selection: Selection | None) -> None:
        self.selection = selection
        if self.source is not None and self.playback is not None:
            self._show_selection(self.source.state_at(self.playback.time_s))

    def select_along_ray(self, origin: Vector, direction: Vector) -> None:
        """Selects what a ray from the camera finds, or clears the selection if nothing."""
        if self.source is None or self.playback is None or self.scene is None:
            return
        state = self.source.state_at(self.playback.time_s)
        shape = self.scene.crane_shape if self.scene.detailed else None
        self.select(select_at(self.scene.layout, self.source, state, origin, direction, shape))

    def select_carried_load(self) -> None:
        if self.selection is None or self.selection.kind != "crane":
            return
        if self.source is not None and self.playback is not None:
            state = self.source.state_at(self.playback.time_s)
            key = state.cranes[self.selection.aisle].carrying
            if key is not None:
                self.select(Selection("load", key=key))

    def go_to_highest_backlog(self) -> None:
        if self.source is None or self.playback is None:
            return
        reported = self.source.describe().reported
        if reported is not None:
            self.playback.pause()
            self.playback.move_to(reported["first_backlog_peak_s"])

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
