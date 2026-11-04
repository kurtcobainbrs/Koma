"""Viewport-sized grid and transient alignment guides, isolated from image controls."""
import math
import flet as ft
import flet.canvas as cv
from koma.ui.retained_container import RetainedCanvas

MAX_GRID_LINES = 256
MIN_GRID_SCREEN_STEP = 12


class ReferenceOverlays:
    def __init__(self, workspace):
        self.workspace = workspace
        self.grid = RetainedCanvas(hold_updates=lambda: False)
        self.guides = RetainedCanvas(hold_updates=lambda: False)
        self.grid_box = ft.Container(left=0, top=0, ignore_interactions=True, content=self.grid)
        self.guide_box = ft.Container(left=0, top=0, ignore_interactions=True, content=self.guides)
        self.key = None

    def sync(self):
        self.refresh_grid()

    def place(self, box):
        ws = self.workspace
        left, top = (-value / ws.zoom for value in ws.translation)
        box.left, box.top = left, top
        box.width, box.height = ws.viewport[0] / ws.zoom, ws.viewport[1] / ws.zoom
        return left, top

    def refresh_grid(self, *, publish=False):
        ws = self.workspace
        self.grid_box.visible = ws.grid_enabled
        step = ws.options['grid_spacing']
        while step * ws.zoom < MIN_GRID_SCREEN_STEP:
            step *= 2
        left, top = self.place(self.grid_box)
        right, bottom = left + ws.viewport[0] / ws.zoom, top + ws.viewport[1] / ws.zoom
        while (right - left + bottom - top) / step > MAX_GRID_LINES:
            step *= 2
        x0 = math.floor((left - ws.extent.x) / step)
        x1 = math.ceil((right - ws.extent.x) / step)
        y0 = math.floor((top - ws.extent.y) / step)
        y1 = math.ceil((bottom - ws.extent.y) / step)
        color = ws.view.settings.configuration.values['appearance']['grid_color']
        key = (ws.grid_enabled, step, x0, x1, y0, y1, ws.extent.x, ws.extent.y, ws.zoom, color, left, top, ws.viewport)
        if key == self.key:
            return
        self.key = key
        paint = ft.Paint(color=color, stroke_width=1 / ws.zoom)
        self.grid.shapes = ([cv.Line(index * step + ws.extent.x - left, 0,
                index * step + ws.extent.x - left, self.grid_box.height, paint)
                for index in range(x0, x1 + 1)] +
            [cv.Line(0, index * step + ws.extent.y - top,
                self.grid_box.width, index * step + ws.extent.y - top, paint)
                for index in range(y0, y1 + 1)]) if ws.grid_enabled else []
        if publish and ws.active:
            ws.view.page.update(self.grid_box)

    def show_guides(self, guides):
        ws = self.workspace
        color = ws.view.settings.configuration.values['appearance']['selection']
        paint = ft.Paint(color=color, stroke_width=1 / ws.zoom)
        left, top = self.place(self.guide_box)
        x, y = guides
        shapes = []
        if x is not None:
            x += ws.extent.x - left
            shapes.append(cv.Line(x, 0, x, self.guide_box.height, paint))
        if y is not None:
            y += ws.extent.y - top
            shapes.append(cv.Line(0, y, self.guide_box.width, y, paint))
        self.guides.shapes = shapes
