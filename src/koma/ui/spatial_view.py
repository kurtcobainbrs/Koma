"""Declarative absolute camera: one patch, no reset/zoom/pan command sequence."""
import flet as ft
from flet.controls.base_control import control
from flet.controls.control_event import Event, EventHandler
from koma.ui.navigation_view import ViewPoseEvent


@control('koma_spatial_view')
class SpatialView(ft.LayoutControl):
    content: ft.Control | None = None
    pan_enabled: bool = False
    scale_enabled: bool = True
    min_scale: float = .05
    max_scale: float = 16
    scale_factor: float = 240
    camera_zoom: float = 1
    camera_x: float = 0
    camera_y: float = 0
    camera_revision: int = 0
    on_pose: EventHandler[ViewPoseEvent] | None = None
    on_camera_start: EventHandler[Event] | None = None

    def set_camera(self, zoom, x, y):
        self.camera_zoom, self.camera_x, self.camera_y = zoom, x, y
        self.camera_revision += 1
