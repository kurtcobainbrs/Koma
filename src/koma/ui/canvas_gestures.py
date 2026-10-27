"""Client-side canvas gestures and their final camera snapshot."""

from dataclasses import dataclass, field

import flet as ft
from flet.controls.base_control import control
from flet.controls.control_event import Event, EventHandler


@dataclass(kw_only=True)
class CanvasNavigationEvent(Event):
    moved: bool = False
    zoom: float = 1.0
    translation_x: float = 0.0
    translation_y: float = 0.0
    local_position: ft.Offset = field(default_factory=lambda: ft.Offset(0, 0))
    global_position: ft.Offset = field(default_factory=lambda: ft.Offset(0, 0))


@control('koma_secondary_pan')
class NativeSecondaryPan(ft.LayoutControl):
    content: ft.Control | None = None
    pan_enabled: bool = True
    reserved_modifiers: list[str] = field(default_factory=list)
    drag_threshold: float = 6
    on_navigation: EventHandler[CanvasNavigationEvent] | None = None
