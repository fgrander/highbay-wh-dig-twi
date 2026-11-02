"""The replay's window: controls, figures, and error messages."""

from typing import Any

import omni.ui as ui

from .core.playback import SPEEDS
from .core.state_source import RunState

ERROR_COLOR = 0xFF4040E0
SPEED_LABELS = [f"{speed:,}×" for speed in SPEEDS]  # noqa: RUF001


def format_time(time_s: float) -> str:
    total = int(time_s)
    return f"{total // 3600:02d}:{total % 3600 // 60:02d}:{total % 60:02d}"


class ReplayWindow:
    def __init__(self, controller: Any) -> None:
        self._controller = controller
        self._moving_slider = False
        self.window = ui.Window("Highbay Replay", width=420, height=300)
        with self.window.frame, ui.VStack(spacing=6):
            with ui.HStack(height=24, spacing=4):
                self._folder = ui.StringField()
                ui.Button("Open", width=60, clicked_fn=self._open)
            self._message = ui.Label("", word_wrap=True, height=0, style={"color": ERROR_COLOR})
            with ui.HStack(height=24, spacing=4):
                self._play = ui.Button("Play", clicked_fn=controller.toggle_playing)
                self._restart = ui.Button("Restart", clicked_fn=controller.restart)
                self._default_view = ui.Button("Default view", clicked_fn=controller.default_view)
            self._slider_model = ui.SimpleFloatModel(0.0)
            self._slider = ui.FloatSlider(self._slider_model, height=24, min=0.0, max=1.0)
            self._slider_model.add_value_changed_fn(self._slider_moved)
            with ui.HStack(height=24, spacing=4):
                ui.Label("Speed", width=50)
                self._speed = ui.ComboBox(SPEEDS.index(60), *SPEED_LABELS)
                self._speed.model.add_item_changed_fn(self._speed_changed)
            self._time = ui.Label("No run is open.", height=0)
        self.set_run_controls(False, False)

    def _open(self) -> None:
        self._controller.open_run_folder(self._folder.model.get_value_as_string())

    def _slider_moved(self, model: Any) -> None:
        if not self._moving_slider:
            self._controller.move_to(model.get_value_as_float())

    def _speed_changed(self, model: Any, _item: Any) -> None:
        index = model.get_item_value_model().get_value_as_int()
        self._controller.set_speed(SPEEDS[index])

    def set_run_controls(self, has_run: bool, can_move_backward: bool) -> None:
        self._play.enabled = has_run
        self._default_view.enabled = has_run
        self._speed.enabled = has_run
        self._restart.enabled = has_run and can_move_backward
        self._slider.enabled = has_run and can_move_backward

    def show_run(self, folder: str | None, time_range: tuple[float, float]) -> None:
        if folder is not None:
            self._folder.model.set_value(folder)
        self.show_time_range(time_range)

    def show_time_range(self, time_range: tuple[float, float]) -> None:
        self._slider.min, self._slider.max = time_range

    def show_message(self, message: str) -> None:
        self._message.text = message

    def show_playing(self, playing: bool) -> None:
        self._play.text = "Pause" if playing else "Play"

    def show_state(self, state: RunState, end_s: float) -> None:
        self._moving_slider = True
        self._slider_model.set_value(state.time_s)
        self._moving_slider = False
        part = "measurement window" if state.in_measurement_window else "warm-up"
        self._time.text = f"{format_time(state.time_s)} of {format_time(end_s)}, {part}"
