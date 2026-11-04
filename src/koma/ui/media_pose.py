"""GPU media positioning with local native gestures and one confirmed event."""
from dataclasses import dataclass
import flet as ft
from flet.controls.base_control import control
from flet.controls.control_event import Event, EventHandler


@dataclass(kw_only=True)
class MediaPoseEvent(Event):
    generation: int = 0
    x: float = 0
    y: float = 0
    scale: float = 1
    rotation: float = 0


@control('koma_media_pose')
class MediaPoseControl(ft.LayoutControl):
    content: ft.Control | None = None
    rect: list[float] | None = None
    x: float = 0
    y: float = 0
    zoom: float = 1
    angle: float = 0
    tool: str = 'move'
    editing: bool = False
    generation: int = 0
    start_request: int = 0
    playback_revision: int = 0
    playing: bool = False
    seconds: float = 0
    maximum_time: float = 3600
    keyframes: list[dict] | None = None
    min_scale: float = .01
    max_scale: float = 100
    max_translation: float = 10
    max_rotation: float = 36000
    on_begin: EventHandler[MediaPoseEvent] | None = None
    on_commit: EventHandler[MediaPoseEvent] | None = None
    on_cancel: EventHandler[MediaPoseEvent] | None = None

    def set_pose(self, pose):
        self.x, self.y, self.zoom, self.angle = pose.x, pose.y, pose.scale, pose.rotation
