"""The replay's window: controls, figures, details, legend, and error messages."""

from typing import Any

import omni.ui as ui

from . import appearance
from .core.display_text import figure_lines, run_identification
from .core.playback import SPEEDS
from .core.state_source import RunState, WarehouseDescription

ERROR_COLOR = 0xFF4040E0
SPEED_LABELS = [f"{speed:,}×" for speed in SPEEDS]  # noqa: RUF001
ACTIVITY_LABELS = (
    ("moving_empty", "Moving empty"),
    ("moving_loaded", "Moving loaded"),
    ("handling", "Handling"),
    ("idle", "Idle"),
)
LEGEND_SWATCH = 14
DOCK_BESIDE = "Property"


def format_time(time_s: float) -> str:
    total = int(time_s)
    return f"{total // 3600:02d}:{total % 3600 // 60:02d}:{total % 60:02d}"


def _ui_color(hex_color: str) -> int:
    red, green, blue = (int(hex_color[index : index + 2], 16) for index in (1, 3, 5))
    return 0xFF000000 | blue << 16 | green << 8 | red


class ReplayWindow:
    def __init__(self, controller: Any) -> None:
        self._controller = controller
        self._moving_slider = False
        self.figures_text: list[str] = []
        self.identification_text: list[str] = []
        self.details_text: list[str] = []
        self.legend_labels: list[str] = []
        self.window = ui.Window("Highbay Replay", width=420, height=640)
        with self.window.frame, ui.ScrollingFrame(), ui.VStack(spacing=6):
            with ui.HStack(height=24, spacing=4):
                self._folder = ui.StringField()
                ui.Button("Open", width=60, clicked_fn=self._open)
            self._message = ui.Label("", word_wrap=True, height=0, style={"color": ERROR_COLOR})
            with ui.HStack(height=24, spacing=4):
                self._play = ui.Button("Play", clicked_fn=controller.toggle_playing)
                self._restart = ui.Button("Restart", clicked_fn=controller.restart)
                self._default_view = ui.Button("Default view", clicked_fn=controller.default_view)
            self._peak = ui.Button(
                "Go to highest backlog", height=24, clicked_fn=controller.go_to_highest_backlog
            )
            self._slider_model = ui.SimpleFloatModel(0.0)
            self._slider = ui.FloatSlider(self._slider_model, height=24, min=0.0, max=1.0)
            self._slider_model.add_value_changed_fn(self._slider_moved)
            with ui.HStack(height=24, spacing=4):
                ui.Label("Speed", width=50)
                self._speed = ui.ComboBox(SPEEDS.index(60), *SPEED_LABELS)
                self._speed.model.add_item_changed_fn(self._speed_changed)
            self._time = ui.Label("No run is open.", height=0)
            self._figures = ui.Label("", word_wrap=True, height=0)
            ui.Separator(height=6)
            self._details = ui.Label("", word_wrap=True, height=0)
            self._carried = ui.Button(
                "Select carried load unit",
                height=24,
                visible=False,
                clicked_fn=controller.select_carried_load,
            )
            ui.Separator(height=6)
            self._legend = ui.VStack(height=0, spacing=2)
            ui.Separator(height=6)
            self._identification = ui.Label("", word_wrap=True, height=0)
        # A floating window over the viewport would cover the warehouse and take its clicks.
        self.window.deferred_dock_in(DOCK_BESIDE, ui.DockPolicy.CURRENT_WINDOW_IS_ACTIVE)
        self.set_run_controls(False, False, False)

    def _open(self) -> None:
        self._controller.open_run_folder(self._folder.model.get_value_as_string())

    def _slider_moved(self, model: Any) -> None:
        if not self._moving_slider:
            self._controller.move_to(model.get_value_as_float())

    def _speed_changed(self, model: Any, _item: Any) -> None:
        index = model.get_item_value_model().get_value_as_int()
        self._controller.set_speed(SPEEDS[index])

    def set_run_controls(self, has_run: bool, can_move_backward: bool, has_peak: bool) -> None:
        self._play.enabled = has_run
        self._default_view.enabled = has_run
        self._speed.enabled = has_run
        self._restart.enabled = has_run and can_move_backward
        self._slider.enabled = has_run and can_move_backward
        self._peak.visible = has_peak
        self._peak.enabled = has_run and can_move_backward

    def show_run(self, folder: str | None, description: WarehouseDescription) -> None:
        if folder is not None:
            self._folder.model.set_value(folder)
        self.identification_text = run_identification(description)
        self._identification.text = "\n".join(self.identification_text)
        self._show_legend(description)
        self.show_details([], None)

    def _show_legend(self, description: WarehouseDescription) -> None:
        entries = [
            (article, appearance.ARTICLE_COLORS[appearance.article_prototype(index)])
            for index, article in enumerate(description.articles)
        ]
        entries += [
            (label, appearance.ACTIVITY_COLORS[activity]) for activity, label in ACTIVITY_LABELS
        ]
        self.legend_labels = [label for label, _ in entries]
        self._legend.clear()
        with self._legend:
            for label, hex_color in entries:
                with ui.HStack(height=LEGEND_SWATCH, spacing=6):
                    ui.Rectangle(
                        width=LEGEND_SWATCH, style={"background_color": _ui_color(hex_color)}
                    )
                    ui.Label(label)

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
        self._time.text = f"{format_time(state.time_s)} of {format_time(end_s)}"
        self.figures_text = figure_lines(state)
        self._figures.text = "\n".join(self.figures_text)

    def show_details(self, lines: list[str], carried: str | None) -> None:
        if lines != self.details_text:
            self.details_text = lines
            self._details.text = "\n".join(lines)
        self._carried.visible = carried is not None
