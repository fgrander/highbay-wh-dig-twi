"""Turns a click in the viewport into a selection ray from the camera."""

from collections.abc import Callable
from typing import Any

import omni.ui.scene as sc
from omni.kit.viewport.utility import get_active_viewport_window
from pxr import Gf

from .core.layout import Vector

# Any depth between the camera's near and far planes gives a point on the ray.
RAY_POINT_DEPTH = 0.5


def ray_at(viewport_api: Any, x: float, y: float) -> tuple[Vector, Vector]:
    """Returns the origin and direction of the ray through a point in normalized coordinates."""
    origin = viewport_api.transform.Transform(Gf.Vec3d(0.0))
    point = viewport_api.ndc_to_world.Transform(Gf.Vec3d(x, y, RAY_POINT_DEPTH))
    direction = point - origin
    return (tuple(origin), tuple(direction))


class ViewportClick:
    def __init__(self, on_ray: Callable[[Vector, Vector], None]) -> None:
        self._on_ray = on_ray
        self._window = get_active_viewport_window()
        self._scene_view = None
        if self._window is None:
            return
        with self._window.get_frame("highbay.replay.click"):
            self._scene_view = sc.SceneView()
            with self._scene_view.scene:
                sc.Screen(gesture=sc.ClickGesture(on_ended_fn=self._clicked))
        self._window.viewport_api.add_scene_view(self._scene_view)

    def _clicked(self, sender: Any) -> None:
        x, y = sender.gesture_payload.mouse
        origin, direction = ray_at(self._window.viewport_api, x, y)
        self._on_ray(origin, direction)
