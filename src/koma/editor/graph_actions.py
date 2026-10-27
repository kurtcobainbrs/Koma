"""Comandos do fluxo e histórico; a interface não contém regras de conexões."""

from dataclasses import replace

import flet as ft

from koma.ui.menus import menu_item, popup_menu

from koma.ui.design import CONTROL_HEIGHT, COMPACT_CONTROL_HEIGHT, dialog, input_style
from koma.editor import graph
from koma.editor.shortcuts import Action


class GraphActions:
    def __init__(self, view):
        self.view, self.page = view, view.page
        self.undo_button = ft.IconButton(icon=ft.Icons.UNDO, tooltip=view.keymap.describe('Desfazer', Action.UNDO),
            width=COMPACT_CONTROL_HEIGHT, height=COMPACT_CONTROL_HEIGHT, on_click=self.undo, disabled=True)
        self.redo_button = ft.IconButton(icon=ft.Icons.REDO, tooltip=view.keymap.describe('Refazer', Action.REDO),
            width=COMPACT_CONTROL_HEIGHT, height=COMPACT_CONTROL_HEIGHT, on_click=self.redo, disabled=True)
        self.menu = popup_menu(icon=ft.Icons.ACCOUNT_TREE_OUTLINED, tooltip='Fluxo e cenas', items=[
            menu_item(view.keymap.describe('Criar moldura', Action.GROUP), on_click=lambda e: self.group_dialog()),
            menu_item('Desconectar', on_click=self.disconnect_selected),
            menu_item('Remover e reconectar', on_click=self.remove_preserving),
        ])

    def sync_history(self):
        locked = self.view.busy or bool(self.view.load_error)
        self.undo_button.disabled = locked or not self.view.history.past
        self.redo_button.disabled = locked or not self.view.history.future
        self.undo_button.tooltip = self.view.keymap.describe(self.view.history.undo_description, Action.UNDO)
        self.redo_button.tooltip = self.view.keymap.describe(self.view.history.redo_description, Action.REDO)

    async def commit(self, board, *, label=None):
        if not self.view.editable():
            return
        self.view.changed(graph.ordered(board), label=label)
        self.view.refresh()
        self.page.update(self.view.content)
        await self.view.workspace.compensate_origin()
        await self.view.persist()

    async def connect(self, source, target):
        if not self.view.editable():
            return
        try:
            await self.commit(graph.connect(self.view.board, source, target))
        except ValueError as exc:
            self.view.notify(str(exc), 'warning')

    async def cut(self, edges):
        await self.commit(graph.disconnect(self.view.board, edges))

    async def disconnect_selected(self, e=None):
        selected = self.view.workspace.navigation.selection.ids
        await self.cut({edge for edge in self.view.board.links if edge.source in selected or edge.target in selected})

    def disconnect_port(self, identifier, output):
        async def disconnected(e):
            await self.cut({edge for edge in self.view.board.links
                if (edge.source if output else edge.target) == identifier})
        return disconnected

    async def organize(self, e=None):
        await self.commit(graph.organize(self.view.board))

    def remove_preserving(self, e=None):
        selected = self.view.workspace.navigation.selection.ids
        self.view.confirm_remove_frames(selected, preserve_flow=True)

    def group_dialog(self, identifier=None):
        if not self.view.editable():
            return
        group = next((group for group in self.view.board.groups if group.id == identifier), None)
        members = frozenset(group.members if group else self.view.workspace.navigation.selection.ids)
        if not members:
            self.view.notify('Selecione os nodes para criar uma moldura.', 'warning')
            return
        field = ft.TextField(label='Nome da moldura', value=group.title if group else f'Grupo {len(self.view.board.groups)+1:02d}',
            max_length=200, counter=ft.Container(width=0, height=0), **input_style())
        error = ft.Text(visible=False, color=ft.Colors.ERROR)
        async def save(e):
            try:
                board = graph.group_frames(self.view.board, members, field.value or '', identifier)
                self.page.pop_dialog()
                await self.commit(board)
            except ValueError as exc:
                error.value, error.visible = str(exc), True
                self.page.update(error)
        self.page.show_dialog(dialog(title=ft.Text('Renomear moldura' if group else 'Agrupar em moldura'),
            content=ft.Column([field, error], width=380, tight=True),
            actions=[ft.TextButton('Cancelar', on_click=lambda e: self.page.pop_dialog()),
                     ft.FilledButton('Salvar', on_click=save)]))

    async def ungroup(self, identifier):
        await self.commit(replace(self.view.board, groups=tuple(group for group in self.view.board.groups if group.id != identifier)))

    async def undo(self, e=None):
        await self.restore(False)

    async def redo(self, e=None):
        await self.restore(True)

    async def restore(self, redo):
        if not self.view.editable():
            return
        workspace = self.view.workspace
        self.view.properties.end_adjust()
        if workspace.drag:
            workspace.cancel_drag(workspace.drag.identifier)
        workspace.box_selection.cancel()
        workspace.links.cancel()
        board = self.view.history.redo(self.view.board) if redo else self.view.history.undo(self.view.board)
        if board == self.view.board:
            return
        self.view.board = board
        self.view.revision += 1
        self.view.title.value = board.title
        self.view.refresh()
        self.sync_history()
        self.page.update(self.view.content)
        await workspace.compensate_origin()
        await self.view.persist()
