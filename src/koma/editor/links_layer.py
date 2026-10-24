"""Sockets, curvas com cache e gestos de corte. Não executa operações em .blends."""

import flet as ft
import flet.canvas as cv

from koma.ui.design import DRAG_INTERVAL_MS
from koma.editor import graph
from koma.editor.shortcuts import Action
from koma.editor.geometry import NODE_WIDTH, NODE_HEIGHT
from koma.editor.wire_geometry import (PORT_Y, INPUT_X, OUTPUT_INSET,
    curve, route, sample_route, crossing, curve_hits_rectangle, distance)


def path_shape(segments, color, width=2):
    return cv.Path([cv.Path.MoveTo(*segments[0][0]),
        *[cv.Path.CubicTo(*b, *c, *d) for _, b, c, d in segments]],
        paint=ft.Paint(color=color, stroke_width=width, style=ft.PaintingStyle.STROKE))


class LinksLayer:
    def __init__(self, workspace):
        self.workspace, self.view, self.page = workspace, workspace.view, workspace.page
        self.canvas = cv.Canvas()
        self.content = ft.Container(content=self.canvas, ignore_interactions=True)
        self.pending = None
        self.drag_pointer = None
        self.drag_endpoint = None
        self.preview_shape = None
        self.cut_points = []
        self.cache = {}
        self.highlighted = set()
        self.candidate = None

    def port(self, identifier, output):
        card = self.view.cards[identifier]
        node = card.content
        height = card.viewport.height if card.viewport.frame.node_type.image else 72
        return node.left + (NODE_WIDTH - OUTPUT_INSET if output else INPUT_X), node.top + height + 52

    def bounds(self, identifier):
        card = self.view.cards[identifier]
        node = card.content
        fallback = card.viewport.height + 68 if card.viewport.frame.node_type.image else 140
        height = self.workspace.node_heights.get(identifier, fallback)
        return node.left, node.top, node.left + NODE_WIDTH, node.top + height

    def refresh(self, update=False):
        self.canvas.width, self.canvas.height = self.workspace.stack.width, self.workspace.stack.height
        edges = set(self.view.board.links)
        self.cache = {edge: value for edge, value in self.cache.items() if edge in edges}
        for edge in self.view.board.links:
            start, end = self.port(edge.source, True), self.port(edge.target, False)
            color = ft.Colors.SECONDARY if edge in self.highlighted or edge == self.candidate else ft.Colors.OUTLINE
            source, target = self.bounds(edge.source), self.bounds(edge.target)
            width = 3 if edge in self.highlighted else 2
            signature = start, end, source, target, color, width
            cached = self.cache.get(edge)
            if cached is None or cached[0] != signature:
                segments = route(start, end, source, target)
                self.cache[edge] = signature, path_shape(segments, color, width), sample_route(segments)
        self.canvas.shapes = [self.cache[edge][1] for edge in self.view.board.links]
        if self.preview_shape:
            self.canvas.shapes.append(self.preview_shape)
        if self.cut_points:
            self.canvas.shapes.append(cv.Path([cv.Path.MoveTo(*self.cut_points[0]),
                *[cv.Path.LineTo(*point) for point in self.cut_points[1:]]],
                paint=ft.Paint(color=ft.Colors.ERROR, stroke_width=2, style=ft.PaintingStyle.STROKE)))
        if update and not self.view.closing:
            self.page.update(self.canvas)

    def highlight_path(self, identifiers):
        highlighted = graph.path_links(self.view.board, identifiers)
        if highlighted != self.highlighted:
            self.highlighted = highlighted
            self.refresh(update=True)

    def begin(self, identifier):
        if not self.view.editable() or self.workspace.navigation.effective_mode != 'select':
            return
        self.pending = identifier
        self.preview_shape = None
        self.workspace.navigation.focus_keyboard()
        self.view.notify(self.view.keymap.describe('Ligue a saída à entrada de outro quadro; cancelar', Action.CANCEL))

    def cancel(self):
        self.pending, self.preview_shape = None, None
        self.drag_pointer, self.drag_endpoint = None, None
        self.refresh(update=True)

    async def accept(self, source, target):
        if not source:
            return
        await self.view.graph.connect(source, target)
        self.cancel()

    def hover(self, e):
        if self.pending and self.pending in self.view.cards and not self.view.closing:
            self.preview_shape = path_shape((curve(self.port(self.pending, True),
                (e.local_position.x, e.local_position.y)),), ft.Colors.SECONDARY)
            self.refresh(update=True)

    def drag_begin(self, identifier, e):
        self.begin(identifier)
        if self.pending != identifier:
            return
        self.drag_pointer = (e.global_position.x, e.global_position.y)
        x, y = self.port(identifier, True)
        self.drag_origin = (x + e.local_position.x - 6, y + e.local_position.y - 6)
        self.drag_endpoint = self.drag_origin
        self.preview_shape = path_shape((curve((x, y), self.drag_endpoint),), ft.Colors.SECONDARY)
        self.refresh(update=True)

    def drag_update(self, e):
        if self.drag_pointer is None or self.pending not in self.view.cards:
            return
        zoom = self.workspace.zoom
        self.drag_endpoint = (
            self.drag_origin[0] + (e.global_position.x - self.drag_pointer[0]) / zoom,
            self.drag_origin[1] + (e.global_position.y - self.drag_pointer[1]) / zoom)
        self.preview_shape = path_shape((curve(self.port(self.pending, True), self.drag_endpoint),), ft.Colors.SECONDARY)
        self.refresh(update=True)

    async def drag_end(self, e=None):
        source, point = self.pending, self.drag_endpoint
        if source and point:
            for identifier in reversed(self.workspace.z_order):
                if identifier == source:
                    continue
                left, top, right, bottom = self.bounds(identifier)
                if left <= point[0] <= right and top <= point[1] <= bottom:
                    if self.view.cards[identifier].viewport.frame.node_type.accepts_input:
                        await self.accept(source, identifier)
                    break
        self.cancel()

    def socket(self, identifier, output):
        circle = ft.Container(width=12, height=12, border_radius=6, bgcolor=ft.Colors.SECONDARY)
        if output:
            return ft.GestureDetector(content=circle, mouse_cursor=ft.MouseCursor.CLICK,
                drag_interval=DRAG_INTERVAL_MS,
                on_tap_down=lambda e: self.begin(identifier),
                on_pan_start=lambda e: self.drag_begin(identifier, e),
                on_pan_update=self.drag_update, on_pan_end=self.drag_end,
                on_pan_cancel=lambda e: self.cancel(),
                tooltip='Saída: arraste até outro quadro para conectar')
        async def clicked(e):
            await self.accept(self.pending, identifier)
        return ft.GestureDetector(content=circle, on_tap_down=clicked,
            mouse_cursor=ft.MouseCursor.CLICK, tooltip='Entrada: receba a saída de outro quadro')

    def cut_begin(self, e):
        nav = self.workspace.navigation
        if self.workspace.grab.active or not self.view.editable() or (nav.effective_mode != 'cut' and not nav.modifier(Action.CUT_DRAG)):
            return
        self.cancel()
        self.cut_points = [(e.local_position.x, e.local_position.y)]
        self.workspace.viewer.scale_enabled = False
        self.refresh(update=True)
        self.page.update(self.workspace.viewer)

    def cut_update(self, e):
        if self.cut_points:
            self.cut_points.append((e.local_position.x, e.local_position.y))
            self.refresh(update=True)

    async def cut_end(self, e=None):
        if not self.cut_points:
            return
        points, self.cut_points = self.cut_points, []
        edges = {edge for edge, cached in self.cache.items() if any(
            crossing(a, b, c, d) for a, b in zip(points, points[1:]) for c, d in zip(cached[2], cached[2][1:]))}
        self.workspace.navigation.sync(update=False)
        self.refresh(update=True)
        self.page.update(self.workspace.viewer)
        if edges:
            await self.view.graph.cut(edges)

    def cancel_cut(self, e=None):
        self.cut_points = []
        self.workspace.navigation.sync(update=False)
        self.refresh(update=True)
        if not self.view.closing:
            self.page.update(self.workspace.viewer)

    def drop_candidate(self, identifier):
        if (not self.view.cards[identifier].viewport.frame.node_type.accepts_input
                or any(identifier in (edge.source, edge.target) for edge in self.view.board.links)):
            return None
        node = self.view.cards[identifier].content
        rect = node.left + 24, node.top + 32, node.left + NODE_WIDTH - 24, node.top + NODE_HEIGHT - 4
        point = node.left + NODE_WIDTH / 2, node.top + PORT_Y
        candidates = [(min(distance(point, a, b) for a, b in zip(cached[2], cached[2][1:])), edge)
            for edge, cached in self.cache.items() if identifier not in (edge.source, edge.target)
            and curve_hits_rectangle(cached[2], rect)]
        return min(candidates, key=lambda item: item[0])[1] if candidates else None
