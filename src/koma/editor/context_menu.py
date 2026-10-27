"""Menu contextual do canvas, com inserção no ponto clicado e comandos de node."""

from inspect import isawaitable

import flet as ft

from koma.editor.geometry import NODE_HEIGHT, NODE_WIDTH, coordinate
from koma.editor.shortcuts import Action
from koma.ui.design import MUTED
from koma.ui.menus import DesktopContextMenu, menu_item, MENU_ICON_SIZE


class CanvasContextMenu:
    def __init__(self, workspace):
        self.workspace, self.view = workspace, workspace.view
        self.pointer = None
        self.items = []
        self.is_open = False
        # Keep the anchor in scene space. Flutter converts local positions using
        # the rendered transform; Python's camera snapshot is not an anchor.
        self.anchor = DesktopContextMenu(content=workspace.pointer_surface,
            secondary_trigger=None, tertiary_trigger=None,
            on_dismiss=self.dismiss, on_select=self.dismiss)
        workspace.viewer.content = self.anchor
        self.content = workspace.navigation.keyboard

    def dismiss(self, e=None, *, refocus=True):
        if not self.is_open:
            return
        self.is_open = False
        if e is None:
            self.view.page.run_task(self.anchor.close)
        if not self.view.closing and self.view.active:
            if refocus:
                self.workspace.navigation.focus_keyboard()

    def item(self, text, icon, handler):
        async def chosen(e=None):
            self.dismiss()
            result = handler(e)
            if isawaitable(result):
                await result
        return menu_item(ft.Text(text),
            icon=ft.Icon(icon, size=MENU_ICON_SIZE, color=MUTED), on_click=chosen)

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
        self.anchor.items = items
        self.is_open = True
        view.page.update(self.anchor)
        try:
            if e is not None and getattr(e, 'global_position', None) is not None:
                await self.anchor.open(global_position=e.global_position)
            else:
                await self.anchor.open(local_position=point)
        except Exception:
            self.is_open = False
            raise
