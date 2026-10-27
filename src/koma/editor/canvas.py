"""Navegação nativa com zoom; arraste atualiza só o node e salva apenas ao soltar."""

import math
import asyncio
from dataclasses import dataclass

import flet as ft
import flet.canvas as cv

from koma.ui.design import BORDER, COMPACT_CONTROL_HEIGHT, CONTROL_HEIGHT, DRAG_INTERVAL_MS, MUTED, ON_SELECTION, RADIUS, SELECTION
from koma.editor.geometry import (GRID_STEP, MAX_ZOOM, MIN_ZOOM, NODE_HEIGHT, NODE_WIDTH,
    ZOOM_STEP, WHEEL_ZOOM_FACTOR, INITIAL_CANVAS_WIDTH, INITIAL_CANVAS_HEIGHT,
    CanvasExtent, frame_bounds, group_delta)
from koma.editor.models import MAX_POSITION
from koma.editor.navigation import CanvasNavigation
from koma.editor.selection import BoxSelection
from koma.editor.box_zoom import BoxZoom
from koma.editor.camera_state import CameraMemory
from koma.editor.grab import GrabMove
from koma.editor.shortcuts import Action
from koma.editor.links_layer import LinksLayer
from koma.editor.group_frames import SceneFrames
from koma.editor.graph import path_links
from koma.editor.context_menu import CanvasContextMenu
from koma.editor.secondary_pointer import SecondaryPointer


@dataclass
class NodeDrag:
    identifier: str
    x: float
    y: float
    pointer_x: float
    pointer_y: float
    zoom: float
    positions: dict[str, tuple[float, float]]
    detach_flow: bool = False


class CanvasViewport(ft.Container):
    """Guarda a câmera antes de o cliente descartar a visualização nativa."""

    def __init__(self, workspace, **kwargs):
        super().__init__(**kwargs)
        self.workspace = workspace

    def will_unmount(self):
        self.workspace.secondary_pointer.cancel(update=False)
        self.workspace.grab.cancel(update=False)
        self.workspace.cancel_camera_transition()
        self.workspace.camera_memory.remember()
        super().will_unmount()


class StoryboardCanvas:
    def __init__(self, view):
        self.view, self.page = view, view.page
        self.zoom = self.gesture_zoom = 1.0
        self.translation_x = self.translation_y = 0.0
        self.initial_view_done = False
        self.initial_framing = False
        self.extent = CanvasExtent()
        self.pending_shift = (0, 0)
        self.viewport_width, self.viewport_height = 1000, 600
        self.drag = None
        self.grab = GrabMove(self)
        self.camera_revision = 0
        self.focusing_region = False
        self.camera_memory = CameraMemory(self)
        self.z_order = []
        self.node_heights = {}
        self.grid_size = None
        self.background = cv.Canvas()
        self.background_hit = ft.GestureDetector(on_tap_down=self.scene_click,
            content=ft.Container(width=INITIAL_CANVAS_WIDTH, height=INITIAL_CANVAS_HEIGHT,
                                 bgcolor=ft.Colors.TRANSPARENT))
        self.stack = ft.Stack(controls=[self.background], width=INITIAL_CANVAS_WIDTH, height=INITIAL_CANVAS_HEIGHT,
            clip_behavior=ft.ClipBehavior.NONE)
        self.links = LinksLayer(self)
        self.scene_frames = SceneFrames(self)
        self.scene = ft.Container(content=view.external_drop.scene(self.stack))
        self.secondary_pointer = SecondaryPointer(self)
        self.pointer_surface = ft.GestureDetector(content=ft.Container(content=self.scene, bgcolor=ft.Colors.TRANSPARENT),
            on_tap_down=self.scene_click,
            on_hover=self.hover, hover_interval=DRAG_INTERVAL_MS, drag_interval=DRAG_INTERVAL_MS,
            on_right_pan_start=self.secondary_pointer.begin, on_right_pan_update=self.secondary_pointer.move,
            on_right_pan_end=self.secondary_pointer.end)
        self.viewer = ft.InteractiveViewer(content=self.pointer_surface, constrained=False, expand=True,
            min_scale=MIN_ZOOM, max_scale=MAX_ZOOM, scale_factor=WHEEL_ZOOM_FACTOR, boundary_margin=MAX_POSITION,
            alignment=ft.Alignment.TOP_LEFT, interaction_update_interval=DRAG_INTERVAL_MS,
            on_interaction_start=self.interaction_start, on_interaction_update=self.interaction_update,
            on_interaction_end=self.interaction_end,
            on_size_change=self.resized)
        self.box_selection = BoxSelection(self)
        self.box_selection.bind(self.background_hit)
        self.box_zoom = BoxZoom(self)
        self.navigation = CanvasNavigation(self)
        self.context_menu = CanvasContextMenu(self)
        self.content = CanvasViewport(self, content=view.external_drop.surface(self.context_menu.content), expand=True, border_radius=RADIUS,
            clip_behavior=ft.ClipBehavior.HARD_EDGE, bgcolor=ft.Colors.SURFACE_CONTAINER_LOW)
        self.zoom_label = ft.TextButton('100%', height=COMPACT_CONTROL_HEIGHT,
            tooltip='100% e centralizar os quadros', on_click=self.reset)
        self.snap_enabled = True
        self.snap = ft.IconButton(width=CONTROL_HEIGHT, height=CONTROL_HEIGHT,
            icon_size=17, on_click=self.toggle_snap)
        self.update_snap()
        self.zoom_out_button = ft.IconButton(icon=ft.Icons.REMOVE, tooltip='Diminuir zoom', icon_size=17,
            width=COMPACT_CONTROL_HEIGHT, height=COMPACT_CONTROL_HEIGHT, on_click=self.zoom_out)
        self.zoom_in_button = ft.IconButton(icon=ft.Icons.ADD, tooltip='Aumentar zoom', icon_size=17,
            width=COMPACT_CONTROL_HEIGHT, height=COMPACT_CONTROL_HEIGHT, on_click=self.zoom_in)
        self.fit_button = ft.IconButton(icon=ft.Icons.FIT_SCREEN, tooltip=view.keymap.describe('Enquadrar tudo', Action.FIT),
            width=COMPACT_CONTROL_HEIGHT, height=COMPACT_CONTROL_HEIGHT, icon_size=17, on_click=self.fit)
        self.controls = ft.Row([
            self.zoom_out_button, self.zoom_label, self.zoom_in_button, self.fit_button,
        ], spacing=2, tight=True, alignment=ft.MainAxisAlignment.END)
        self.navigation.sync(update=False)

    def refresh(self):
        ids = set(self.view.cards)
        self.navigation.reconcile()
        self.navigation.editing_fields = {field for field in self.navigation.editing_fields if field[0] in ids}
        self.node_heights = {key: value for key, value in self.node_heights.items() if key in ids}
        self.z_order = [identifier for identifier in self.z_order if identifier in ids]
        self.z_order.extend(frame.id for frame in self.view.board.frames if frame.id not in self.z_order)
        dx, dy = self.extent.include(self.view.board.frames)
        self.pending_shift = self.pending_shift[0] + dx, self.pending_shift[1] + dy
        for frame in self.view.board.frames:
            node = self.view.cards[frame.id].content
            node.left, node.top, node.width = frame.x + self.extent.origin_x, frame.y + self.extent.origin_y, NODE_WIDTH
        self.stack.width, self.stack.height = self.extent.width, self.extent.height
        self.scene_frames.refresh()
        self.links.highlighted = path_links(self.view.board, self.navigation.selection.ids)
        self.links.refresh()
        self.rebuild_stack()
        size = self.stack.width, self.stack.height
        if size != self.grid_size:
            self.grid_size = size
            paint = ft.Paint(color=ft.Colors.with_opacity(0.4, BORDER), stroke_width=0.6)
            self.background.width, self.background.height = size
            self.background_hit.content.width, self.background_hit.content.height = size
            self.background.shapes = [cv.Line(x, 0, x, size[1], paint=paint)
                for x in range(0, math.ceil(size[0]), GRID_STEP)] + [
                cv.Line(0, y, size[0], y, paint=paint) for y in range(0, math.ceil(size[1]), GRID_STEP)]

    def rebuild_stack(self):
        self.stack.controls = [self.background, self.background_hit, *self.scene_frames.controls(), self.links.content,
            *[self.view.cards[key].content for key in self.z_order], self.box_selection.overlay, self.box_zoom.overlay]

    def update_groups(self):
        self.scene_frames.refresh()
        return self.scene_frames.controls()

    def resized(self, e):
        if e.width > 0 and e.height > 0:
            self.viewport_width, self.viewport_height = e.width, e.height

    def node_resized(self, identifier, e):
        if e.height > 0 and self.node_heights.get(identifier) != e.height:
            self.node_heights[identifier] = e.height
            self.links.refresh(update=True)
            if self.view.board.groups:
                self.page.update(*self.update_groups())

    def interaction_start(self, e):
        if self.focusing_region or self.box_zoom.active:
            return
        self.cancel_camera_transition()
        self.gesture_zoom = self.zoom

    def interaction_update(self, e):
        if self.focusing_region or self.box_zoom.active or self.drag or self.box_selection.active or self.view.closing or not math.isfinite(e.scale) or e.scale <= 0:
            return
        value = max(MIN_ZOOM, min(MAX_ZOOM, self.gesture_zoom * e.scale))
        focal = getattr(e, 'local_focal_point', None)
        delta = getattr(e, 'focal_point_delta', None)
        if focal is not None and delta is not None:
            ratio = value / self.zoom
            # O Flutter também informa o deslocamento do ponteiro quando pan
            # está desativado. Esse deslocamento não move a câmera real.
            dx, dy = (delta.x, delta.y) if self.viewer.pan_enabled else (0, 0)
            self.translation_x = focal.x - (focal.x - dx - self.translation_x) * ratio
            self.translation_y = focal.y - (focal.y - dy - self.translation_y) * ratio
        if abs(value - self.zoom) > 0.001:
            self.zoom = value
            self.update_label()
        self.camera_memory.remember()

    def interaction_end(self, e):
        self.camera_memory.remember()

    def update_label(self):
        self.zoom_label.content = f'{self.zoom:.0%}'
        if not self.view.closing:
            self.page.update(self.zoom_label)

    async def set_zoom(self, value, anchor=None):
        if self.drag or self.box_selection.active or self.box_zoom.active or self.view.closing or self.view.busy:
            return
        self.cancel_camera_transition()
        value = max(MIN_ZOOM, min(MAX_ZOOM, value))
        previous = self.zoom
        anchor = anchor or ((self.viewport_width / 2 - self.translation_x) / previous,
                            (self.viewport_height / 2 - self.translation_y) / previous)
        await self.viewer.zoom(value / previous)
        self.zoom = self.gesture_zoom = value
        await self.pan_by(anchor[0] * (previous / value - 1), anchor[1] * (previous / value - 1))
        self.update_label()
        self.camera_memory.remember()

    async def pan_by(self, dx, dy):
        if dx or dy:
            await self.viewer.pan(dx, dy)
            self.translation_x += self.zoom * dx
            self.translation_y += self.zoom * dy

    async def zoom_at_scene(self, point, factor):
        if point is not None:
            await self.set_zoom(self.zoom * factor, anchor=(point.x, point.y))

    async def scene_click(self, e):
        await self.navigation.background_click(e)

    def hover(self, e):
        self.context_menu.pointer = (e.local_position.x, e.local_position.y)
        self.grab.hover(e)
        if not self.grab.active:
            self.links.hover(e)

    async def scene_secondary_click(self, e):
        if self.navigation.effective_mode == 'zoom':
            await self.navigation.secondary_click(e)
        else:
            await self.context_menu.open(e)

    async def zoom_in(self, e):
        await self.set_zoom(self.zoom * ZOOM_STEP)

    async def zoom_out(self, e):
        await self.set_zoom(self.zoom / ZOOM_STEP)

    async def reset(self, e=None):
        identifiers = self.navigation.selection.ids or None
        await self.focus_nodes(identifiers, scale=1.0)

    async def fit(self, e=None):
        await self.focus_nodes()

    async def focus_nodes(self, identifiers=None, scale=None):
        if self.drag or self.box_selection.active or self.box_zoom.active or self.view.closing or self.view.busy:
            return
        self.cancel_camera_transition()
        frames = [frame for frame in self.view.board.frames if identifiers is None or frame.id in identifiers]
        left, top, right, bottom = frame_bounds(frames, self.node_heights)
        margin = GRID_STEP * 3
        # F aproxima a seleção; Home mantém a visão geral em até 100%.
        limit = MAX_ZOOM if identifiers is not None else 1.0
        value = scale if scale is not None else min(max(1, self.viewport_width - 2 * margin) / (right - left),
            max(1, self.viewport_height - 2 * margin) / (bottom - top), limit)
        value = max(MIN_ZOOM, min(MAX_ZOOM, value))
        await self.viewer.reset()
        self.translation_x = self.translation_y = 0
        await self.viewer.zoom(value)
        self.zoom = self.gesture_zoom = value
        await self.pan_by(self.viewport_width / (2 * value) - (left + right) / 2 - self.extent.origin_x,
                          self.viewport_height / (2 * value) - (top + bottom) / 2 - self.extent.origin_y)
        self.initial_view_done = True
        self.pending_shift = 0, 0
        self.update_label()
        self.camera_memory.remember()

    def cancel_camera_transition(self):
        self.camera_revision += 1

    async def focus_region(self, bounds):
        """A caixa já usa coordenadas do canvas, incluindo sua origem expandida."""
        if self.focusing_region or self.view.closing or self.view.busy or self.drag or self.box_selection.active or self.box_zoom.active:
            return
        if not all(math.isfinite(value) for value in bounds):
            return
        left, top, right, bottom = bounds
        if right <= left or bottom <= top:
            return
        margin = GRID_STEP
        target = max(MIN_ZOOM, min(MAX_ZOOM,
            max(1, self.viewport_width - 2 * margin) / (right - left),
            max(1, self.viewport_height - 2 * margin) / (bottom - top)))
        target_x = self.viewport_width / 2 - (left + right) / 2 * target
        target_y = self.viewport_height / 2 - (top + bottom) / 2 * target
        self.cancel_camera_transition()
        # Uma transformação absoluta evita acumular erros entre zoom/pan e
        # elimina a disputa de doze etapas animadas com eventos nativos atrasados.
        self.focusing_region = True
        self.viewer.scale_enabled = self.viewer.pan_enabled = False
        self.page.update(self.viewer)
        try:
            await self.viewer.reset()
            self.zoom = self.gesture_zoom = 1.0
            self.translation_x = self.translation_y = 0.0
            await self.viewer.zoom(target)
            self.zoom = self.gesture_zoom = target
            await self.pan_by(target_x / target, target_y / target)
            self.initial_view_done = True
            self.pending_shift = 0, 0
            self.update_label()
            self.camera_memory.remember()
        finally:
            self.focusing_region = False
            self.navigation.sync(update=False)
            if not self.view.closing and self.view.active:
                self.page.update(self.viewer)

    async def restore_camera(self):
        state = self.camera_memory.state
        if state is None:
            await self.fit()
            return
        await self.viewer.reset()
        self.translation_x = self.translation_y = 0
        await self.viewer.zoom(state.zoom)
        self.zoom = self.gesture_zoom = state.zoom
        await self.pan_by(self.viewport_width / (2 * state.zoom) - state.center_x - self.extent.origin_x,
                          self.viewport_height / (2 * state.zoom) - state.center_y - self.extent.origin_y)
        self.initial_view_done = True
        self.pending_shift = 0, 0
        self.update_label()

    async def resume(self):
        # Ao remontar o controle, o cliente nativo reinicia a matriz de transformação.
        self.cancel_camera_transition()
        revision = self.camera_revision
        await asyncio.sleep(.04)
        if revision == self.camera_revision and not self.view.closing and not self.view.busy:
            await self.restore_camera()

    async def ensure_initial_view(self):
        if self.initial_view_done or self.initial_framing or self.view.closing or not self.view.board.frames:
            return
        self.initial_framing = True
        try:
            # Aguarda a primeira composição e a leitura das alturas, sem bloquear a UI.
            await asyncio.sleep(0.04)
            for _ in range(25):
                if self.initial_view_done or self.view.closing:
                    return
                if not self.view.busy:
                    await self.restore_camera()
                    return
                await asyncio.sleep(0.02)
        finally:
            self.initial_framing = False

    async def compensate_origin(self):
        dx, dy = self.pending_shift
        self.pending_shift = 0, 0
        if self.initial_view_done and (dx or dy):
            await self.pan_by(-dx, -dy)

    def update_snap(self):
        self.snap.icon = ft.Icons.GRID_ON if self.snap_enabled else ft.Icons.GRID_OFF
        self.snap.tooltip = 'Snap na grade ativado' if self.snap_enabled else 'Snap na grade desativado'
        self.snap.style = ft.ButtonStyle(bgcolor=SELECTION if self.snap_enabled else None,
            color=ON_SELECTION if self.snap_enabled else MUTED)

    def toggle_snap(self, e):
        if self.view.busy or self.view.closing:
            return
        # A opção vale para o próximo arraste; não move quadros já posicionados.
        self.snap_enabled = not self.snap_enabled
        self.update_snap()
        self.page.update(self.snap)
        if hasattr(self.view, 'chrome'):
            self.view.chrome.sync()
            self.page.update(self.view.chrome.content)

    def begin_drag(self, identifier, e):
        if not self.view.editable() or self.drag or self.navigation.effective_mode != 'select':
            return
        frame = next((f for f in self.view.board.frames if f.id == identifier), None)
        if frame is None:
            return
        if identifier not in self.navigation.selection.ids and self.navigation.modifier(Action.ADD_SELECTION):
            self.navigation.apply_selection(self.navigation.selection.ids | {identifier}, identifier)
        else:
            self.navigation.select_node(identifier, focus=True)
        positions = {f.id: (f.x, f.y) for f in self.view.board.frames if f.id in self.navigation.selection.ids}
        self.drag = NodeDrag(identifier, frame.x, frame.y, e.global_position.x, e.global_position.y, self.zoom, positions)
        self.drag.detach_flow = self.navigation.drag_detach_active()
        if self.drag.detach_flow:
            self.links.candidate = None
            self.links.refresh(update=True)
        self.viewer.pan_enabled = self.viewer.scale_enabled = False
        self.z_order = [key for key in self.z_order if key not in positions] + [key for key in self.z_order if key in positions]
        self.raise_node(identifier)
        self.view.cards[identifier].highlight(True, is_active=True)
        self.page.update(self.viewer)

    def raise_node(self, identifier):
        if self.view.closing or identifier not in self.z_order:
            return
        self.z_order.remove(identifier)
        self.z_order.append(identifier)
        self.rebuild_stack()
        self.page.update(self.stack)

    def update_drag(self, identifier, e):
        drag = self.drag
        if drag is None or drag.identifier != identifier or self.view.closing:
            return
        dx, dy = group_delta(drag.positions, (e.global_position.x - drag.pointer_x) / drag.zoom,
                            (e.global_position.y - drag.pointer_y) / drag.zoom, anchor=(drag.x, drag.y))
        positions = {key: (x + dx, y + dy) for key, (x, y) in drag.positions.items()}
        nodes = []
        for key, (x, y) in positions.items():
            node = self.view.cards[key].content
            left, top = self.extent.origin_x + x, self.extent.origin_y + y
            if (node.left, node.top) != (left, top):
                node.left, node.top = left, top
                nodes.append(node)
        drag.detach_flow = self.navigation.drag_detach_active()
        self.links.candidate = self.links.drop_candidate(identifier) if len(drag.positions) == 1 and not drag.detach_flow else None
        self.links.refresh(update=True)
        self.page.update(*nodes, *self.update_groups())

    async def end_drag(self, identifier, e=None):
        if self.drag is None or self.drag.identifier != identifier:
            return
        drag, self.drag = self.drag, None
        self.grab.active = False
        self.navigation.sync(update=False)
        if self.view.closing:
            return
        node = self.view.cards[identifier].content
        dx, dy = group_delta(drag.positions, node.left - self.extent.origin_x - drag.x,
            node.top - self.extent.origin_y - drag.y, anchor=(drag.x, drag.y), snap=self.snap_enabled)
        await self.view.position_frames({key: (x + dx, y + dy) for key, (x, y) in drag.positions.items()}, insert_flow=True,
            detach_flow=drag.detach_flow and self.navigation.drag_detach_active())
        self.page.update(self.viewer)

    def cancel_drag(self, identifier, e=None, *, update=True):
        if self.drag is None or self.drag.identifier != identifier:
            return
        drag, self.drag = self.drag, None
        self.grab.active = False
        self.navigation.sync(update=False)
        for frame in self.view.board.frames:
            node = self.view.cards[frame.id].content
            node.left, node.top = frame.x + self.extent.origin_x, frame.y + self.extent.origin_y
        self.links.candidate = None
        self.links.refresh()
        self.update_groups()
        if update and not self.view.closing:
            self.page.update(self.viewer)
