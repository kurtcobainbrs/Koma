"""Reference commands share the document/history; decoding never runs in gestures."""
import asyncio
from dataclasses import replace
from pathlib import Path
from uuid import uuid4
from PIL import Image
import flet as ft
from flet.controls.exceptions import FletException
from koma.documents.images import import_image, IMAGE_EXTENSIONS
from koma.image_clipboard import copy_image
from koma.editor.reference_models import ReferenceImage, MAX_REFERENCES, MIN_REFERENCE_SIZE, MAX_REFERENCE_POSITION, REFERENCE_GAP


class ReferenceActions:
    def __init__(self, canvas):
        self.canvas, self.view = canvas, canvas.view

    async def copy_image(self, e=None):
        if not self.canvas.active or not self.view.editable():
            return
        item = next((item for item in self.view.board.references
            if item.id == self.canvas.selection.active), None)
        if item is None:
            self.view.notify('Selecione uma imagem.', 'info')
            return
        try:
            await copy_image(self.view.store.images / item.asset)
            self.view.notify('Imagem copiada.', 'success')
        except (OSError, ValueError, RuntimeError, FletException) as exc:
            self.view.notify(f'Não foi possível copiar: {exc}', 'warning')

    async def send_to_canvas(self, e=None):
        if not self.canvas.active or not self.view.editable() or self.canvas.gesture:
            return
        selected = tuple((item.asset, item.title) for item in self.view.board.references
            if item.id in self.canvas.selection.ids)
        try:
            identifiers = await self.view.image_input.create_from_assets(selected, label='Enviar referências ao Canvas')
            if identifiers:
                self.view.work_modes.show_canvas()
                self.view.notify(f'{len(identifiers)} quadros criados.', 'success')
        except (OSError, ValueError, RuntimeError, FletException) as exc:
            self.view.notify(f'Não foi possível enviar: {exc}', 'warning')

    async def commit(self, items, label, *, expected=None):
        view = self.view
        if not view.editable() or not self.canvas.active or (expected is not None and view.board is not expected):
            self.canvas.models.clear()
            self.canvas.sync()
            return False
        board = replace(view.board, references=tuple(items))
        try:
            board.validate()
        except ValueError as exc:
            self.canvas.cancel()
            view.notify(str(exc), 'warning')
            return False
        if board == view.board:
            self.canvas.models.clear()
            self.canvas.sync()
            return False
        view.changed(board, label=label)
        self.canvas.sync()
        view.page.update(self.canvas.scene, self.canvas.tools)
        await view.persist()
        return True

    async def duplicate(self, e=None):
        if not self.canvas.active or not self.view.editable():
            return
        canvas, board = self.canvas, self.view.board
        chosen = [item for item in board.references if item.id in canvas.selection.ids]
        if len(board.references) + len(chosen) > MAX_REFERENCES:
            self.view.notify(f'Limite de {MAX_REFERENCES} referências atingido.', 'warning')
            return
        offset = self.view.settings.configuration.values['references']['duplicate_offset']
        if chosen:
            offset = min(offset, *(MAX_REFERENCE_POSITION - max(item.x, item.y) for item in chosen))
        copies = tuple(replace(item, id=uuid4().hex, x=item.x + offset, y=item.y + offset) for item in chosen)
        if copies:
            canvas.selection.replace({item.id for item in copies})
            await self.commit((*board.references, *copies), 'Duplicar referências', expected=board)

    async def delete(self, e=None):
        if not self.canvas.active or not self.view.editable():
            return
        board = self.view.board
        await self.commit((item for item in board.references if item.id not in self.canvas.selection.ids),
            'Excluir referências', expected=board)

    async def pick(self, e=None):
        if not self.view.editable() or not self.canvas.active:
            return
        board, session = self.view.board, self.view.session
        try:
            files = await ft.FilePicker().pick_files(dialog_title='Importar referências', allow_multiple=True,
                file_type=ft.FilePickerFileType.CUSTOM, allowed_extensions=IMAGE_EXTENSIONS,
                initial_directory=self.view.settings.configuration.values['files']['import_folder'] or None)
            if files and self.canvas.active and self.view.board is board and self.view.session is session:
                await self.import_paths([item.path for item in files if item.path])
        except (OSError, ValueError, RuntimeError, FletException) as exc:
            self.view.notify(f'Não foi possível importar: {exc}', 'warning')

    async def import_paths(self, paths, position=None):
        await self._import([(import_image, Path(path)) for path in paths], position)

    async def paste(self, e=None):
        board, session = self.view.board, self.view.session
        try:
            importer, source = await self.view.image_input.clipboard_source()
            if self.canvas.active and self.view.board is board and self.view.session is session:
                await self._import([(importer, source)])
        except (OSError, ValueError, RuntimeError, FletException) as exc:
            self.view.notify(f'Não foi possível colar: {exc}', 'warning')

    async def _import(self, sources, position=None):
        view, canvas = self.view, self.canvas
        if not view.editable() or not canvas.active or canvas.loading:
            return
        board, session = view.board, view.session
        remaining = MAX_REFERENCES - len(board.references)
        if len(sources) > remaining:
            view.notify(f'O projeto aceita até {MAX_REFERENCES} referências.', 'warning')
            return
        x, y = position or canvas.insertion_position()
        width = view.settings.configuration.values['references']['image_width']
        imported, failures = [], 0
        # Import sequentially to bound decoded-image memory. One undo for the batch.
        canvas.loading = True
        try:
            for importer, source in sources:
                if not canvas.active or view.session is not session or view.board is not board or not view.editable():
                    return
                try:
                    name, _ = await asyncio.to_thread(importer, source, view.store)
                    def size():
                        with Image.open(view.store.images / name) as image:
                            return image.size
                    iw, ih = await asyncio.to_thread(size)
                    ratio = ih / iw
                    w = max(width, MIN_REFERENCE_SIZE / min(1, ratio))
                    item = ReferenceImage(asset=name, title=source.stem[:200] if isinstance(source, Path) else 'Colada',
                        x=x, y=y, width=w, height=w * ratio)
                    item.validate()
                    imported.append(item)
                    x += item.width + REFERENCE_GAP
                except (OSError, ValueError, RuntimeError):
                    failures += 1
            if view.session is session and view.board is board and canvas.active and imported:
                canvas.selection.replace({item.id for item in imported})
                await self.commit((*board.references, *imported), 'Importar referências', expected=board)
            if failures:
                view.notify(f'{failures} imagem(ns) não puderam ser importadas.', 'warning')
        finally:
            canvas.loading = False
