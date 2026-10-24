"""Molduras de cenas derivadas dos membros; mover o título move a cena inteira."""

import flet as ft

from koma.ui.design import BORDER, DRAG_INTERVAL_MS, MUTED, RADIUS, SURFACE
from koma.ui.typography import FONT_HEADING, TEXT_BODY
from koma.editor.geometry import GRID_STEP, NODE_HEIGHT, NODE_WIDTH


class SceneFrames:
    def __init__(self, workspace):
        self.workspace, self.view = workspace, workspace.view
        self.boxes, self.headers = {}, {}

    def refresh(self):
        identifiers = {group.id for group in self.view.board.groups}
        self.boxes = {key: value for key, value in self.boxes.items() if key in identifiers}
        self.headers = {key: value for key, value in self.headers.items() if key in identifiers}
        for group in self.view.board.groups:
            if group.id not in self.boxes:
                self.boxes[group.id] = ft.Container(ignore_interactions=True,
                    border=ft.Border.all(1, BORDER), border_radius=RADIUS,
                    bgcolor=ft.Colors.with_opacity(.045, ft.Colors.SECONDARY))
                menu = ft.PopupMenuButton(icon=ft.Icons.MORE_HORIZ, padding=0, items=[
                    ft.PopupMenuItem('Renomear moldura', on_click=self.rename(group.id)),
                    ft.PopupMenuItem('Desagrupar', on_click=self.ungroup(group.id))])
                title = ft.GestureDetector(expand=True, mouse_cursor=ft.MouseCursor.MOVE,
                    drag_interval=DRAG_INTERVAL_MS, on_tap_down=self.select(group.id),
                    on_pan_start=self.start(group.id), on_pan_update=self.drag(group.id),
                    on_pan_end=self.end(group.id), on_pan_cancel=self.cancel(group.id),
                    content=ft.Text(group.title, size=TEXT_BODY, font_family=FONT_HEADING, max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS))
                self.headers[group.id] = ft.Container(height=32, bgcolor=SURFACE, padding=ft.Padding.only(left=8),
                    border_radius=RADIUS, content=ft.Row([title, menu], spacing=4))
            self.headers[group.id].content.controls[0].content.value = group.title
            self.update_bounds(group)

    def update_bounds(self, group):
        nodes = [self.view.cards[key].content for key in group.members]
        left, top = min(node.left for node in nodes) - GRID_STEP, min(node.top for node in nodes) - GRID_STEP * 2
        right = max(node.left + NODE_WIDTH for node in nodes) + GRID_STEP
        bottom = max(self.view.cards[key].content.top + self.workspace.node_heights.get(key, NODE_HEIGHT)
                     for key in group.members) + GRID_STEP
        box, header = self.boxes[group.id], self.headers[group.id]
        box.left, box.top, box.width, box.height = left, top, right - left, bottom - top
        header.left, header.top, header.width = left, top, right - left

    def controls(self):
        return [control for group in self.view.board.groups for control in (self.boxes[group.id], self.headers[group.id])]

    def group(self, identifier):
        return next((group for group in self.view.board.groups if group.id == identifier), None)

    def select(self, identifier):
        def selected(e):
            group = self.group(identifier)
            if group and self.workspace.navigation.effective_mode == 'select':
                self.workspace.navigation.apply_selection(group.members)
                self.workspace.navigation.focus_keyboard()
        return selected

    def start(self, identifier):
        def started(e):
            group = self.group(identifier)
            if group:
                self.select(identifier)(e)
                self.workspace.begin_drag(group.members[0], e)
        return started

    def drag(self, identifier):
        def moved(e):
            group = self.group(identifier)
            if group:
                self.workspace.update_drag(group.members[0], e)
        return moved

    def end(self, identifier):
        async def ended(e):
            group = self.group(identifier)
            if group:
                await self.workspace.end_drag(group.members[0], e)
        return ended

    def cancel(self, identifier):
        def cancelled(e):
            group = self.group(identifier)
            if group:
                self.workspace.cancel_drag(group.members[0], e)
        return cancelled

    def rename(self, identifier):
        def renamed(e):
            self.view.graph.group_dialog(identifier)
        return renamed

    def ungroup(self, identifier):
        async def removed(e):
            await self.view.graph.ungroup(identifier)
        return removed
