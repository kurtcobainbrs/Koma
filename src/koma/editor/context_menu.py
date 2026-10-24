"""Menu contextual do canvas, com inserção no ponto clicado e comandos de node."""

from inspect import isawaitable

import flet as ft

from koma.editor.geometry import NODE_HEIGHT, NODE_WIDTH, coordinate
from koma.editor.shortcuts import Action
from koma.ui.design import BORDER, MUTED


class CanvasContextMenu:
    def __init__(self, workspace):
        self.workspace, self.view = workspace, workspace.view
        self.pointer = None
        self.items = []
        self.popup = ft.Container(width=208, padding=ft.Padding.symmetric(vertical=4),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH, border=ft.Border.all(1, BORDER), border_radius=2)
        barrier = ft.GestureDetector(content=ft.Container(bgcolor=ft.Colors.TRANSPARENT, expand=True),
            on_tap=self.dismiss, on_secondary_tap_down=self.dismiss)
        self.layer = ft.Stack([barrier, self.popup], fit=ft.StackFit.EXPAND, visible=False)
        self.content = ft.Stack([workspace.navigation.keyboard, self.layer], fit=ft.StackFit.EXPAND)

    def dismiss(self, e=None, *, refocus=True):
        if not self.layer.visible:
            return
        self.layer.visible = False
        if not self.view.closing and self.view.active:
            self.view.page.update(self.layer)
            if refocus:
                self.workspace.navigation.focus_keyboard()

    def item(self, text, icon, handler):
        async def chosen(e=None):
            self.dismiss()
            result = handler(e)
            if isawaitable(result):
                await result
        return ft.MenuItemButton(content=ft.Text(text, size=13), leading=ft.Icon(icon, size=18, color=MUTED),
            height=34, on_click=chosen,
            style=ft.ButtonStyle(animation_duration=0, overlay_color=ft.Colors.TRANSPARENT,
                bgcolor={ft.ControlState.HOVERED: ft.Colors.SURFACE_CONTAINER_HIGHEST},
                padding=ft.Padding.symmetric(horizontal=8), shape=ft.RoundedRectangleBorder(radius=0)))

    async def open_insert(self):
        await self.open(insertion_only=True)

    async def open(self, e=None, *, insertion_only=False):
        view, ws = self.view, self.workspace
        if not view.editable() or ws.navigation.modifier(Action.CUT_DRAG):
            return
        if e is not None:
            self.pointer = (e.local_position.x, e.local_position.y)
        x, y = self.pointer or ((ws.viewport_width / 2 - ws.translation_x) / ws.zoom,
                                 (ws.viewport_height / 2 - ws.translation_y) / ws.zoom)
        point = ft.Offset(x, y)
        position = (coordinate(point.x - ws.extent.origin_x, snap=ws.snap_enabled),
                    coordinate(point.y - ws.extent.origin_y, snap=ws.snap_enabled))
        hit = next((identifier for identifier in reversed(ws.z_order)
            if identifier in view.cards and
            view.cards[identifier].content.left <= point.x <= view.cards[identifier].content.left + NODE_WIDTH and
            view.cards[identifier].content.top <= point.y <= view.cards[identifier].content.top + ws.node_heights.get(identifier, NODE_HEIGHT)), None)
        items = []
        if hit and not insertion_only:
            if hit not in ws.navigation.selection.ids:
                ws.navigation.select_node(hit, focus=True)
            selected = frozenset(ws.navigation.selection.ids)
            muted = all(frame.muted for frame in view.board.frames if frame.id in selected)
            async def toggle(e=None):
                await view.toggle_muted(selected)
            async def duplicate(e=None):
                await view.duplicate_frames(selected)
            items.extend([
                self.item(view.keymap.describe('Desmutar' if muted else 'Mutar', Action.MUTE), ft.Icons.VISIBILITY_OFF, toggle),
                self.item('Duplicar', ft.Icons.CONTENT_COPY, duplicate),
                self.item('Excluir', ft.Icons.DELETE_OUTLINE, lambda e: view.confirm_remove_frames(selected)),
            ])
        def insert(kind):
            async def add(e=None):
                count = len(view.board.frames)
                await view.add_node(kind, position=position)
                if len(view.board.frames) > count:
                    ws.navigation.select_node(view.board.frames[-1].id, focus=True)
            return add
        items.extend([
            self.item('Início de cena', ft.Icons.MOVIE_OUTLINED, insert('main')),
            self.item('Quadro', ft.Icons.ADD, insert('frame')),
            self.item('Importar imagens…', ft.Icons.ADD_PHOTO_ALTERNATE_OUTLINED, view.pick_images),
        ])
        self.items = items
        self.popup.content = ft.Column(items, spacing=0, tight=True)
        self.popup.left = max(0, min(x * ws.zoom + ws.translation_x, ws.viewport_width - 208))
        self.popup.top = max(0, min(y * ws.zoom + ws.translation_y, ws.viewport_height - (len(items) * 34 + 8)))
        self.layer.visible = True
        view.page.update(self.layer)
        ws.navigation.focus_keyboard()
