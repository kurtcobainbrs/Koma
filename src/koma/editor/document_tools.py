"""Dialogs for recent projects, node search, asset inspection and project merge."""

import asyncio
from pathlib import Path
import flet as ft
from flet.controls.exceptions import FletException
from koma.documents.session import DocumentSession
from koma.editor.geometry import place_missing
from koma.editor.node_clipboard import capture_selection
from koma.ui.design import dialog, input_style, MUTED, COMPACT_CONTROL_HEIGHT
from koma.ui.menus import menu_item


class DocumentTools:
    def __init__(self, application):
        self.app = application

    def show_list(self, title, controls, search=None):
        body = ft.ListView(controls=controls, height=320, spacing=2)
        self.app.page.show_dialog(dialog(title=ft.Text(title),
            content=ft.Column(([search] if search else []) + [body], width=520, tight=True),
            actions=[ft.TextButton('Fechar', on_click=lambda e: self.app.page.pop_dialog())]))
        return body

    def recent_items(self, before_open=None):
        items = []
        for value in self.app.recent.paths:
            path = Path(value)
            async def open_path(e=None, target=path):
                if before_open:
                    before_open()
                await self.app.open_project(target)
            items.append(menu_item(path.name, tooltip=str(path), on_click=open_path, disabled=not path.is_file()))
        return items or [menu_item('Nenhum arquivo', disabled=True)]

    def recent(self, e=None):
        controls = [ft.TextButton(command.content, tooltip=command.tooltip, on_click=command.on_click,
            disabled=command.disabled, height=COMPACT_CONTROL_HEIGHT)
            for command in self.recent_items(self.app.page.pop_dialog)]
        self.show_list('Recentes', controls)

    def search(self, e=None):
        view = self.app.view
        field = ft.TextField(label='Buscar quadros e cenas', autofocus=True, **input_style())
        def results():
            query = (field.value or '').casefold()
            controls = []
            for index, frame in enumerate(view.board.frames, 1):
                if query not in ' '.join((frame.title, frame.action, frame.notes, frame.audio, frame.subtitle)).casefold():
                    continue
                async def locate(e=None, identifier=frame.id):
                    if self.app.view is not view or not view.editable():
                        return
                    self.app.page.pop_dialog()
                    view.workspace.navigation.set_mode('select')
                    view.workspace.navigation.select_node(identifier, focus=True)
                    await view.workspace.focus_nodes({identifier})
                controls.append(ft.TextButton(f'{index:02d} · {frame.title or frame.node_type.label}', on_click=locate,
                    height=COMPACT_CONTROL_HEIGHT))
            return controls or [ft.Text('Nenhum resultado.', color=MUTED)]
        body = self.show_list('Localizar', results(), field)
        def changed(e):
            body.controls = results()
            self.app.page.update(body)
        field.on_change = changed

    async def media(self, e=None):
        view = self.app.view
        board, session, store = view.board, view.session, view.store
        assets = {}
        for frame in board.frames:
            if frame.image:
                assets.setdefault(frame.image, []).append(frame)
        controls = []
        def inspect_assets():
            from PIL import Image
            dimensions = {}
            for asset in assets:
                try:
                    with Image.open(store.images / asset) as image:
                        dimensions[asset] = f'{image.width} × {image.height}'
                except (OSError, ValueError):
                    dimensions[asset] = 'Arquivo indisponível'
            return dimensions
        dimensions = await asyncio.to_thread(inspect_assets)
        if self.app.view is not view or view.board is not board or view.session is not session or not view.editable():
            return
        for asset, frames in assets.items():
            async def locate(e=None, ids=frozenset(f.id for f in frames)):
                if self.app.view is not view or not view.editable():
                    return
                self.app.page.pop_dialog()
                view.workspace.navigation.set_mode('select')
                view.workspace.navigation.apply_selection(set(ids))
                await view.workspace.focus_nodes(ids)
            controls.append(ft.ListTile(title=ft.Text(frames[0].title or 'Imagem'),
                subtitle=ft.Text(f'{dimensions[asset]} · {len(frames)} usos · {asset}', size=12),
                leading=ft.Icon(ft.Icons.IMAGE_OUTLINED), dense=True, on_click=locate))
        for track in board.audio_tracks:
            controls.append(ft.ListTile(title=ft.Text(track.title),
                subtitle=ft.Text(f'{track.duration:g} s · {track.asset}', size=12),
                leading=ft.Icon(ft.Icons.AUDIO_FILE_OUTLINED), dense=True))
        self.show_list('Mídias do projeto', controls or [ft.Text('Nenhuma mídia importada.', color=MUTED)])

    async def import_project(self, e=None):
        view = self.app.view
        if not view.editable():
            return
        board, target_session = view.board, view.session
        session = None
        try:
            files = await ft.FilePicker().pick_files(dialog_title='Importar nodes de outro projeto',
                allow_multiple=False, allowed_extensions=['koma'], file_type=ft.FilePickerFileType.CUSTOM)
            if not files or not files[0].path or not view.editable():
                return
            session = await asyncio.to_thread(DocumentSession.open, files[0].path, self.app.settings.directory)
            source = place_missing(session.board)
            payload = await capture_selection(source, session.store, {frame.id for frame in source.frames})
            if view.board is not board or view.session is not target_session or self.app.view is not view:
                raise ValueError('O projeto de destino mudou durante a importação. Tente novamente.')
            await self.app.node_clipboard.insert(view, payload, operation='Importar projeto')
        except (OSError, ValueError, RuntimeError, FletException) as exc:
            view.notify(f'Não foi possível importar o projeto: {exc}', 'error')
        finally:
            if session:
                await asyncio.to_thread(session.close)
