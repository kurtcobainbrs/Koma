"""Right-button navigation: release clicks, pan drags, preserve explicit cuts."""

import asyncio
import math

import flet as ft
from koma.ui.event_updates import explicit_updates

from koma.editor.shortcuts import Action
from koma.ui import drop_runtime
from koma.ui.canvas_gestures import NativeSecondaryPan

PAN_DRAG_THRESHOLD = 6  # Logical screen pixels, independent of canvas zoom.


class SecondaryPointer:
    def __init__(self, workspace):
        self.workspace = workspace
        self.press = self.last = None
        self.panning = self.cutting = False
        self.lock = asyncio.Lock()
        self.native = None

    def surface(self, content):
        if not drop_runtime.enabled():
            return content
        self.native = NativeSecondaryPan(content=content,
            drag_threshold=PAN_DRAG_THRESHOLD, on_navigation=self.native_navigation)
        return self.native

    def sync(self):
        if self.native is not None:
            ws = self.workspace
            self.native.pan_enabled = (ws.view.editable() and not ws.grab.active
                and ws.navigation.effective_mode != 'cut' and not ws.drag
                and not ws.box_selection.active and not ws.box_zoom.active and not ws.focusing_region)
            self.native.reserved_modifiers = list(ws.view.keymap.bindings(Action.CUT_DRAG))
            self.native.zoom_modifiers = list(ws.view.keymap.bindings(Action.DRAG_ZOOM))
            self.native.zoom_enabled = self.native.pan_enabled
            self.native.zoom_sensitivity = ws.view.settings.configuration.values['canvas']['zoom']

    @explicit_updates
    async def native_navigation(self, e):
        ws = self.workspace
        if ws.view.closing or not ws.view.active:
            return
        if not all(math.isfinite(value) for value in (e.zoom, e.translation_x, e.translation_y)) or e.zoom <= 0:
            return
        ws.zoom = ws.gesture_zoom = e.zoom
        ws.translation_x, ws.translation_y = e.translation_x, e.translation_y
        ws.camera_memory.remember()
        if e.moved:
            ws.navigation.focus_keyboard()
        else:
            await ws.scene_secondary_click(e)

    @explicit_updates
    def begin(self, e):
        ws = self.workspace
        if ws.grab.active:
            ws.grab.cancel()
            return
        if (not ws.view.editable() or ws.drag or ws.box_selection.active
                or ws.box_zoom.active or ws.focusing_region):
            return
        self.cutting = (ws.navigation.effective_mode == 'cut'
            or ws.navigation.modifier(Action.CUT_DRAG))
        if self.native is not None and not self.cutting:
            ws.cancel_camera_transition()
            return
        self.press = e
        self.last = (e.global_position.x, e.global_position.y)
        if self.cutting:
            ws.links.cut_begin(e)
        else:
            ws.cancel_camera_transition()
            ws.viewer.pan_enabled = ws.viewer.scale_enabled = False
            ws.page.update(ws.viewer)

    @explicit_updates
    async def move(self, e):
        async with self.lock:
            await self._move(e)

    async def _move(self, e):
        if self.press is None:
            return
        ws = self.workspace
        if self.cutting:
            ws.links.cut_update(e)
            return
        x, y = e.global_position.x, e.global_position.y
        if not all(math.isfinite(value) for value in (x, y)):
            return
        if not self.panning:
            origin = self.press.global_position
            if math.hypot(x - origin.x, y - origin.y) < PAN_DRAG_THRESHOLD:
                return
            self.panning = True
            ws.navigation.focus_keyboard()
            ws.pointer_surface.mouse_cursor = ft.MouseCursor.GRABBING
            ws.page.update(ws.pointer_surface)
        previous, self.last = self.last, (x, y)
        await ws.pan_by((x - previous[0]) / ws.zoom, (y - previous[1]) / ws.zoom)
        ws.camera_memory.remember()

    @explicit_updates
    async def end(self, e):
        async with self.lock:
            if self.press is None:
                return
            # Include the final movement even when Flutter throttled move events.
            await self._move(e)
            press, panning, cutting = self.press, self.panning, self.cutting
            self.press = self.last = None
            self.panning = self.cutting = False
            if cutting:
                await self.workspace.links.cut_end(e)
            self.workspace.navigation.sync()
            if not panning and not cutting:
                await self.workspace.scene_secondary_click(press)

    def cancel(self, *, update=True):
        active = self.press is not None
        self.press = self.last = None
        self.panning = self.cutting = False
        if active:
            if self.workspace.links.cut_points:
                self.workspace.links.cancel_cut()
            self.workspace.navigation.sync(update=update)
