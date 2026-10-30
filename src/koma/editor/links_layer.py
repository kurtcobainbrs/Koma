"""Sockets, curvas com cache e gestos de corte. Não executa operações em .blends."""

import flet as ft
from koma.ui.event_updates import explicit_updates
import flet.canvas as cv

from koma.ui.design import DRAG_INTERVAL_MS
from koma.editor import graph
from koma.editor.shortcuts import Action
from koma.editor.geometry import NODE_WIDTH, GRID_STEP
from koma.ui.node_layout import NODE_LAYOUT
from koma.editor.group_ports import GroupPort
from koma.editor.wire_geometry import (
    route, sample_route, crossing, curve_hits_rectangle, distance)

MAX_CUT_PREVIEW_POINTS = 2048


def path_shape(segments, color, width=2):
    return cv.Path([cv.Path.MoveTo(*segments[0][0]),
        *[cv.Path.CubicTo(*b, *c, *d) for _, b, c, d in segments]],
        paint=ft.Paint(color=color, stroke_width=width, style=ft.PaintingStyle.STROKE))


class LinksLayer:
    def __init__(self, workspace):
        self.workspace, self.view, self.page = workspace, workspace.view, workspace.page
        self.canvas = cv.Canvas()
        self.gesture_canvas = cv.Canvas()
        self.layer = ft.Stack([self.canvas, self.gesture_canvas])
        self.content = ft.Container(content=self.layer, ignore_interactions=True)
        self.pending = None
        self.drag_pointer = None
        self.drag_endpoint = None
        self.preview_shape = None
        self.cut_points = []
        self.cut_hits = set()
        self.cut_board = None
        self.cache = {}
        self.highlighted = set()
        self.candidate = None
        self.detached_source = self.detached_members = self.detached_board = None

    def port(self, identifier, output, *, bounds=None):
        if isinstance(identifier, GroupPort):
            left, top, right, bottom = self.bounds(identifier)
            inset = NODE_LAYOUT.inset + NODE_LAYOUT.socket_size / 2
            return (right - inset if output else left + inset, (top + bottom) / 2)
        identifier = self.workspace.scope.representative(identifier)
        left, top, right, bottom = self.bounds(identifier) if bounds is None else bounds
        layout = self.view.cards[identifier].layout
        return (right - layout.socket_inset if output else left + layout.socket_inset,
            top + layout.socket_y(bottom - top, compact=self.view.cards[identifier].viewport.frame.node_type.starts_scene))

    def bounds(self, identifier):
        if isinstance(identifier, GroupPort):
            return self.workspace.sequence_ports.bounds(identifier)
        identifier = self.workspace.scope.representative(identifier)
        card = self.view.cards[identifier]
        node = card.content
        body_height = (card.composite_body.content.height if card.composite_body else
            card.viewport.height if card.viewport.frame.node_type.image else card.main_body.height)
        fallback = card.layout.height(body_height, compact=card.viewport.frame.node_type.starts_scene)
        height = self.workspace.node_heights.get(identifier, fallback)
        return node.left, node.top, node.left + card.width, node.top + height

    def refresh(self, update=False):
        self.canvas.width, self.canvas.height = self.workspace.stack.width, self.workspace.stack.height
        self.gesture_canvas.width, self.gesture_canvas.height = self.canvas.width, self.canvas.height
        self.layer.width, self.layer.height = self.canvas.width, self.canvas.height
        board = self.view.board
        drag = self.workspace.drag
        if drag and drag.detach_flow:
            members = frozenset(self.view.sequences.index.closure(drag.positions))
            if self.detached_source is not board or self.detached_members != members:
                self.detached_source, self.detached_members = board, members
                self.detached_board = graph.detach(board, members)
            board = self.detached_board
        else:
            self.detached_source = self.detached_members = self.detached_board = None
        visible_edges = tuple(edge for edge, _, _ in self.workspace.scope.edges(board))
        edges = set(visible_edges)
        self.cache = {edge: value for edge, value in self.cache.items() if edge in edges}
        bounds = {}
        for edge in visible_edges:
            for identifier in (edge.source, edge.target):
                if identifier not in bounds:
                    bounds[identifier] = self.bounds(identifier)
            source, target = bounds[edge.source], bounds[edge.target]
            start, end = self.port(edge.source, True, bounds=source), self.port(edge.target, False, bounds=target)
            color = ft.Colors.ON_SURFACE if edge in self.highlighted or edge == self.candidate else ft.Colors.ON_SURFACE_VARIANT
            width = 3 if edge in self.highlighted else 2
            signature = start, end, source, target, color, width
            cached = self.cache.get(edge)
            if cached is None or cached[0] != signature:
                if cached is not None and cached[0][:4] == signature[:4]:
                    shape = cached[1]
                    shape.paint.color, shape.paint.stroke_width = color, width
                    self.cache[edge] = signature, shape, cached[2]
                else:
                    segments = route(start, end, source, target)
                    self.cache[edge] = signature, path_shape(segments, color, width), sample_route(segments)
        self.canvas.shapes = [self.cache[edge][1] for edge in visible_edges]
        if update and not self.view.closing:
            self.page.update(self.canvas)

    def highlight_path(self, identifiers, *, update=True):
        highlighted = graph.path_links(self.view.board, self.view.sequences.index.closure(identifiers))
        if highlighted != self.highlighted:
            self.highlighted = highlighted
            self.refresh(update=update)
            return True
        return False

    @explicit_updates
    def begin(self, identifier):
        if not self.view.editable() or self.workspace.navigation.effective_mode != 'select':
            return
        self.pending = identifier
        self.preview_shape = None
        self.workspace.navigation.focus_keyboard()
        self.view.notify(self.view.keymap.describe('Ligue a saída à entrada de outro quadro; cancelar', Action.CANCEL))

    @explicit_updates
    def cancel(self):
        if self.pending is None and self.preview_shape is None and self.drag_pointer is None:
            return
        self.pending, self.preview_shape = None, None
        self.drag_pointer, self.drag_endpoint = None, None
        self.refresh_gesture()

    def refresh_gesture(self):
        """Update transient geometry without traversing established connections."""
        shapes = [self.preview_shape] if self.preview_shape else []
        if self.cut_points:
            shapes.append(cv.Path([cv.Path.MoveTo(*self.cut_points[0]),
                *[cv.Path.LineTo(*point) for point in self.cut_points[1:]]],
                paint=ft.Paint(color=ft.Colors.ERROR, stroke_width=2, style=ft.PaintingStyle.STROKE)))
        self.gesture_canvas.shapes = shapes
        if not self.view.closing:
            self.page.update(self.gesture_canvas)

    async def accept(self, source, target):
        if not source:
            return
        await self.view.graph.connect(source, target)
        self.cancel()

    @explicit_updates
    def hover(self, e):
        if self.valid_endpoint(self.pending) and not self.view.closing:
            self.update_preview((e.local_position.x, e.local_position.y))

    def update_preview(self, endpoint):
        self.preview_shape = cv.Line(*self.port(self.pending, True), *endpoint,
            paint=ft.Paint(color=ft.Colors.SECONDARY, stroke_width=2))
        self.refresh_gesture()

    def valid_endpoint(self, identifier):
        return identifier in self.view.cards or identifier in self.workspace.sequence_ports.boxes

    @explicit_updates
    def drag_begin(self, identifier, e):
        self.begin(identifier)
        if self.pending != identifier:
            return
        self.drag_pointer = (e.global_position.x, e.global_position.y)
        x, y = self.port(identifier, True)
        radius = NODE_LAYOUT.socket_size / 2
        self.drag_origin = (x + e.local_position.x - radius, y + e.local_position.y - radius)
        self.drag_endpoint = self.drag_origin
        self.update_preview(self.drag_endpoint)

    @explicit_updates
    def drag_update(self, e):
        if self.drag_pointer is None or not self.valid_endpoint(self.pending):
            return
        zoom = self.workspace.zoom
        self.drag_endpoint = (
            self.drag_origin[0] + (e.global_position.x - self.drag_pointer[0]) / zoom,
            self.drag_origin[1] + (e.global_position.y - self.drag_pointer[1]) / zoom)
        self.update_preview(self.drag_endpoint)

    @explicit_updates
    async def drag_end(self, e=None):
        source, point = self.pending, self.drag_endpoint
        if source and point:
            for ref in self.workspace.sequence_ports.boxes:
                left, top, right, bottom = self.bounds(ref)
                if ref.output and left <= point[0] <= right and top <= point[1] <= bottom:
                    await self.accept(source, ref)
                    self.cancel()
                    return
            for identifier in reversed(self.workspace.z_order):
                if identifier == source:
                    continue
                if not self.view.cards[identifier].content.visible:
                    continue
                left, top, right, bottom = self.bounds(identifier)
                if left <= point[0] <= right and top <= point[1] <= bottom:
                    if self.view.cards[identifier].viewport.frame.node_type.accepts_input:
                        await self.accept(source, identifier)
                    break
        self.cancel()

    def socket(self, identifier, output):
        circle = ft.Container(width=NODE_LAYOUT.socket_size, height=NODE_LAYOUT.socket_size,
            border_radius=NODE_LAYOUT.socket_size / 2, bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1.5, ft.Colors.ON_SURFACE_VARIANT))
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

    @explicit_updates
    def cut_begin(self, e):
        nav = self.workspace.navigation
        if self.workspace.grab.active or not self.view.editable() or (nav.effective_mode != 'cut' and not nav.modifier(Action.CUT_DRAG)):
            return
        self.cancel()
        self.cut_points = [(e.local_position.x, e.local_position.y)]
        self.cut_board = self.view.board
        self.cut_hits.clear()
        self.workspace.viewer.scale_enabled = False
        self.refresh_gesture()
        self.workspace.update_interaction()

    @explicit_updates
    def cut_update(self, e):
        if self.cut_points:
            if self.cut_board is not self.view.board:
                self.cancel_cut()
                return
            point = (e.local_position.x, e.local_position.y)
            previous = self.cut_points[-1]
            if point == previous:
                return
            for edge, cached in self.cache.items():
                if edge not in self.cut_hits and any(crossing(previous, point, a, b)
                        for a, b in zip(cached[2], cached[2][1:])):
                    self.cut_hits.add(edge)
            self.cut_points.append(point)
            del self.cut_points[:-MAX_CUT_PREVIEW_POINTS]
            self.refresh_gesture()

    @explicit_updates
    async def cut_end(self, e=None):
        if not self.cut_points:
            return
        if e is not None and getattr(e, 'local_position', None) is not None:
            self.cut_update(e)
        edges = set(self.cut_hits) if self.cut_board is self.view.board else set()
        self.cut_points = []
        self.cut_hits.clear()
        self.cut_board = None
        self.workspace.navigation.sync(update=False)
        self.refresh_gesture()
        self.workspace.update_interaction()
        if edges:
            await self.view.graph.cut(edges)

    @explicit_updates
    def cancel_cut(self, e=None):
        if not self.cut_points:
            return
        self.cut_points = []
        self.cut_hits.clear()
        self.cut_board = None
        self.workspace.navigation.sync(update=False)
        self.refresh_gesture()
        self.workspace.update_interaction()

    def drop_candidate(self, identifier):
        if (self.view.cards[identifier].viewport.frame.node_type.contains_frames
                or not self.view.cards[identifier].viewport.frame.node_type.accepts_input
                or any(identifier in (edge.source, edge.target) for edge in self.view.board.links)):
            return None
        left, top, right, bottom = self.bounds(identifier)
        rect = (left + GRID_STEP, top + NODE_LAYOUT.header_height + NODE_LAYOUT.spacing,
            right - GRID_STEP, bottom - NODE_LAYOUT.padding)
        point = (left + right) / 2, self.port(identifier, True)[1]
        edges = set(self.view.board.links)
        candidates = [(min(distance(point, a, b) for a, b in zip(cached[2], cached[2][1:])), edge)
            for edge, cached in self.cache.items() if edge in edges and identifier not in (edge.source, edge.target)
            and curve_hits_rectangle(cached[2], rect)]
        return min(candidates, key=lambda item: item[0])[1] if candidates else None
