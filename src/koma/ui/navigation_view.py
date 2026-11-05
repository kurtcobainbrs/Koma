"""Native camera controls; no node state and no Python pointer-move traffic."""
from dataclasses import dataclass, field
import flet as ft
from flet.controls.base_control import control
from flet.controls.control_event import Event, EventHandler
from koma.ui import drop_runtime
from koma.ui.event_updates import explicit_updates
from koma.ui.retained_container import RetainedContainer, retain_children


@dataclass(kw_only=True)
class ViewZoomEvent(Event):
    factor: float = 1
    anchor_x: float = 0
    pixels: float = 0
    generation: int = 0


@dataclass(kw_only=True)
class ViewPoseEvent(Event):
    zoom: float = 1
    x: float = 0
    y: float = 0
    generation: int = 0


@control('koma_navigation')
class NativeNavigation(ft.LayoutControl):
    content: ft.Control | None = None
    mode: str = 'preview'
    navigation_enabled: bool = True
    minimum_zoom: float = .25
    maximum_zoom: float = 16
    wheel_sensitivity: float = 1
    pan_speed: float = 1
    zoom_modifiers: list[str] = field(default_factory=list)
    content_coordinates: bool = False
    generation: int = 0
    revision: int = 0
    scroll_request: int = 0
    scroll_offset: float = 0
    initial_zoom: float = 1
    initial_x: float = 0
    initial_y: float = 0
    on_zoom: EventHandler[ViewZoomEvent] | None = None
    on_pose: EventHandler[ViewPoseEvent] | None = None
    on_activate: EventHandler[Event] | None = None
    on_deactivate: EventHandler[Event] | None = None
    on_engage: EventHandler[Event] | None = None

    async def fit(self):
        await self._invoke_method('fit', timeout=5)


class PreviewNavigation:
    def __init__(self, player):
        self.player = player
        self.body = RetainedContainer(hold_updates=lambda: False,
            expand=True, content=player.screen, alignment=ft.Alignment.CENTER)
        self.native = drop_runtime.supports('navigation_v1')
        self.content = NativeNavigation(content=self.body, expand=True,
            on_activate=self.activate, on_deactivate=self.deactivate, on_pose=self.pose, on_engage=self.engage) if self.native else ft.InteractiveViewer(
                content=self.body, expand=True, pan_enabled=False, min_scale=.25, max_scale=16)
        self.configure()

    def configure(self):
        options = self.player.view.settings.configuration.values['animatic']
        minimum, maximum = options['preview_min_zoom'] / 100, options['preview_max_zoom'] / 100
        if self.native:
            from koma.editor.shortcuts import Action
            self.content.zoom_modifiers = list(self.player.view.keymap.bindings(Action.DRAG_ZOOM))
            self.content.minimum_zoom, self.content.maximum_zoom = minimum, maximum
            self.content.wheel_sensitivity = options['preview_wheel_sensitivity']
            self.content.pan_speed = options['preview_pan_speed']
        else:
            self.content.min_scale, self.content.max_scale = minimum, maximum
            self.content.scale_factor = 240 / options['preview_wheel_sensitivity']

    @property
    def zoom(self):
        return self.content.initial_zoom if self.native else 1

    @explicit_updates
    def activate(self, e=None):
        self.player.navigation_target = 'preview'

    @explicit_updates
    def deactivate(self, e=None):
        self.player.navigation_target = 'timeline'

    @explicit_updates
    def engage(self, e=None):
        if self.player.presenting:
            self.activate()
            self.player.view.properties.release_field_focus()
            self.player.focus_timeline()

    @explicit_updates
    def pose(self, e):
        import math
        if e.generation == self.content.generation and e.zoom > 0 and all(math.isfinite(value) for value in (e.zoom, e.x, e.y)):
            self.content.initial_zoom, self.content.initial_x, self.content.initial_y = e.zoom, e.x, e.y

    def lock(self, locked, *, update=True):
        if self.native:
            self.content.navigation_enabled = not locked
        else:
            self.content.scale_enabled = not locked
        if update and self.player.presenting:
            with retain_children(self.body):
                self.player.view.page.update(self.content)

    async def fit(self, e=None):
        if self.player.presenting and not self.player.editing:
            if self.native:
                await self.content.fit()
            else:
                await self.content.reset()
