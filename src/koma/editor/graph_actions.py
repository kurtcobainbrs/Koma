"""Comandos do fluxo e histórico; a interface não contém regras de conexões."""

from dataclasses import replace
import asyncio
from koma.documents.images import load_thumbnails
from koma.editor.models import Storyboard, StoryLink

import flet as ft

from koma.ui.menus import menu_item, popup_menu, menu_separator

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
        self.commands = {
            'group': menu_item(view.keymap.describe('Criar moldura…', Action.GROUP),
                icon=ft.Icons.CROP_FREE, on_click=lambda e: self.group_dialog()),
            'sequence': menu_item(view.keymap.describe('Criar sequência', Action.SEQUENCE),
                icon=ft.Icons.VIEW_TIMELINE_OUTLINED, on_click=view.node_handler('sequence')),
            'organize': menu_item('Organizar', icon=ft.Icons.ACCOUNT_TREE_OUTLINED, on_click=self.organize),
            'disconnect': menu_item('Desconectar', icon=ft.Icons.LINK_OFF, on_click=self.disconnect_selected),
            'remove_preserving': menu_item('Remover e reconectar', icon=ft.Icons.DELETE_OUTLINE,
                on_click=self.remove_preserving),
        }
        self.menu = popup_menu(icon=ft.Icons.ACCOUNT_TREE_OUTLINED, tooltip='Fluxo e cenas', items=[
            self.commands['group'], self.commands['sequence'], menu_separator(), self.commands['organize'], menu_separator(),
            self.commands['disconnect'], self.commands['remove_preserving']])

    def sync_history(self):
        locked = self.view.busy or bool(self.view.load_error)
        self.undo_button.disabled = locked or not self.view.history.past
        self.redo_button.disabled = locked or not self.view.history.future
        self.undo_button.tooltip = self.view.keymap.describe(self.view.history.undo_description, Action.UNDO)
        self.redo_button.tooltip = self.view.keymap.describe(self.view.history.redo_description, Action.REDO)

    async def commit(self, board, *, label=None):
        if not self.view.editable():
            return
        previous = self.view.snapshot_presentations()
        self.view.changed(board, label=label)
        self.view.refresh()
        self.view.publish(previous)
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
        try:
            await self.commit(graph.disconnect(self.view.board, edges))
        except ValueError as exc:
            self.view.notify(str(exc), 'warning')

    async def disconnect_selected(self, e=None):
        selected = self.view.workspace.navigation.selection.ids
        index = self.view.sequences.index
        containers = {key for key in selected if index.nodes[key].node_type.contains_frames}
        selected = index.closure(selected)
        edges = {edge for edge in self.view.board.links if edge.source in selected or edge.target in selected}
        edges.update(edge for edge, _, _ in self.view.workspace.scope.edges()
            if edge.source in selected or edge.target in selected)
        if containers:
            edges = {edge for edge in edges if not containers.intersection(index.ancestors(edge.source)).intersection(
                index.ancestors(edge.target))}
        await self.cut(edges)

    def disconnect_port(self, identifier, output):
        async def disconnected(e):
            try:
                endpoint = self.view.sequences.index.endpoint(identifier, output)
            except ValueError:
                return
            await self.cut({edge for edge, _, _ in self.view.workspace.scope.edges()
                if (edge.source if output else edge.target) == endpoint})
        return disconnected

    async def organize(self, e=None):
        board = self.view.board
        visible = self.view.workspace.scope.visible
        projection = self.view.workspace.scope
        placed = graph.layout_positions(tuple(frame for frame in board.frames if frame.id in visible),
            tuple(StoryLink(source, target) for _, source, target in projection.edges()
                if source in visible and target in visible))
        await self.commit(replace(board, frames=tuple(replace(frame, x=placed[frame.id][0], y=placed[frame.id][1])
            if frame.id in placed else frame for frame in board.frames)))

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
        self.page.show_dialog(dialog(title=ft.Text('Renomear moldura' if group else 'Agrupar em moldura'), on_confirm=save,
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
        before = self.view.board
        board = self.view.history.redo(before) if redo else self.view.history.undo(before)
        if board == self.view.board:
            return
        self.view.board = board
        if replace(board, references=before.references, media_filter=before.media_filter) == before:
            self.view.revision += 1
            references_changed = board.references != before.references
            if references_changed:
                self.view.references.models.clear()
                self.view.references.sync()
            self.sync_history()
            self.view.chrome.sync()
            if references_changed and self.view.references.active:
                self.page.update(self.view.references.scene, self.view.references.tools,
                    self.view.chrome.content, self.view.chrome.status)
            else:
                self.page.update(self.view.chrome.content)
            await self.view.persist()
            return
        missing = tuple(frame for frame in board.frames if frame.image and frame.image not in self.view.thumbnails)
        if missing:
            self.view.lock(True)
            try:
                self.view.thumbnails.update(await asyncio.to_thread(load_thumbnails, Storyboard(frames=missing), self.view.store))
            except (OSError, ValueError) as exc:
                self.view.notify(f'Não foi possível carregar a prévia: {exc}', 'warning')
            finally:
                self.view.lock(False)
        self.view.revision += 1
        self.view.title.value = board.title
        self.view.refresh()
        self.sync_history()
        self.page.update(self.view.content)
        await workspace.compensate_origin()
        await self.view.persist()
