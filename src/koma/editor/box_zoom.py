"""Enquadramento por retângulo; não altera seleção nem o documento."""

import flet as ft
from koma.ui.event_updates import explicit_updates

from koma.editor.selection import rectangle


class BoxZoom:
    def __init__(self, workspace):
        self.workspace = workspace
        self.start = self.pending = None
        self.bounds = None
        self.overlay = ft.Container(left=0, top=0, width=0, height=0, visible=False,
            ignore_interactions=True, border=ft.Border.all(1, ft.Colors.SECONDARY),
            bgcolor=ft.Colors.with_opacity(.14, ft.Colors.SECONDARY))

    @property
    def active(self):
        return self.start is not None

    @explicit_updates
    def press(self, e):
        if self.workspace.navigation.effective_mode == 'zoom' and self.workspace.view.editable() and not self.workspace.focusing_region:
            self.workspace.cancel_camera_transition()
            self.pending = e.local_position.x, e.local_position.y

    @explicit_updates
    def begin(self, e):
        if self.workspace.navigation.effective_mode != 'zoom' or not self.workspace.view.editable() or self.workspace.focusing_region:
            return
        self.start = self.pending or (e.local_position.x, e.local_position.y)
        self.pending = None
        self.workspace.navigation.focus_keyboard()
        self.workspace.viewer.scale_enabled = False
        self.workspace.update_interaction()
        self.update(e)

    @explicit_updates
    def update(self, e):
        if not self.active or self.workspace.view.closing:
            return
        self.bounds = rectangle(self.start, (e.local_position.x, e.local_position.y))
        left, top, right, bottom = self.bounds
        self.overlay.left, self.overlay.top = left, top
        self.overlay.width, self.overlay.height = right - left, bottom - top
        self.overlay.visible = True
        self.workspace.page.update(self.overlay)

    @explicit_updates
    async def end(self, e=None):
        bounds = self.bounds if self.active else None
        self.cancel()
        # Desconsidera cliques e pequenos movimentos involuntários, em pixels da tela.
        if bounds and min(bounds[2] - bounds[0], bounds[3] - bounds[1]) * self.workspace.zoom >= 8:
            await self.workspace.focus_region(bounds)

    @explicit_updates
    def cancel(self, e=None):
        if self.start is None and self.pending is None and self.bounds is None:
            return
        self.start = self.pending = self.bounds = None
        self.overlay.visible = False
        self.workspace.navigation.sync(update=False)
        if not self.workspace.view.closing:
            self.workspace.update_interaction(self.overlay)
