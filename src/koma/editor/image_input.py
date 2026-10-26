"""Entrada de imagens no quadro ativo, isolada da edição e da geometria."""

import asyncio
from pathlib import Path
from dataclasses import replace

import flet as ft
from koma.editor.shortcuts import Action
from flet.controls.exceptions import FletException, FletUnsupportedPlatformException

from koma.documents.images import IMAGE_EXTENSIONS, import_image, import_image_bytes
from koma.editor.models import MAX_CARDS, StoryFrame
from koma.editor.geometry import coordinate


class StoryboardImageInput:
    def __init__(self, view):
        self.view = view

    async def drop(self, paths, position, identifier=None):
        """Destino capturado no drop, validado antes de qualquer alteração."""
        view = self.view
        if not view.editable():
            return
        if len(paths) != 1:
            view.notify('Solte uma imagem por vez sobre um quadro ou no canvas.', 'warning')
            return
        frame = next((item for item in view.board.frames if item.id == identifier), None)
        if identifier is not None and (frame is None or not frame.node_type.image):
            view.notify('Este node não aceita imagens. Solte sobre um quadro ou no espaço vazio.', 'warning')
            return
        if identifier is None and len(view.board.frames) >= MAX_CARDS:
            view.notify(f'Limite de {MAX_CARDS} quadros atingido.', 'warning')
            return
        source = Path(paths[0])
        session, revision = view.session, view.revision
        view.properties.end_adjust()
        view.workspace.context_menu.dismiss(refocus=False)
        if view.workspace.drag:
            view.workspace.cancel_drag(view.workspace.drag.identifier)
        view.lock(True)
        try:
            if not source.is_file() or source.suffix.lower().lstrip('.') not in IMAGE_EXTENSIONS:
                raise ValueError('Escolha uma imagem PNG, JPEG, WebP, BMP ou TIFF.')
            view.notify(f'Importando {source.name}…', 'working')
            name, data = await asyncio.to_thread(import_image, source, view.store)
            if view.closing or not view.active or view.session is not session or view.revision != revision:
                return
            if identifier is not None:
                updated = view.board.change(identifier, image=name, crop_x=0, crop_y=0)
            else:
                x, y = (coordinate(n, snap=view.workspace.snap_enabled) for n in position)
                frame = StoryFrame(title=source.stem, image=name, x=x, y=y)
                updated = replace(view.board, frames=(*view.board.frames, frame))
                updated.validate()
                identifier = frame.id
            view.thumbnails[name] = data
            view.changed(updated)
            view.refresh()
            view.workspace.navigation.apply_selection({identifier}, identifier)
            view.page.update(view.content)
            if await view.persist():
                view.notify('Imagem importada. Use Desfazer para reverter.', 'success')
        except (OSError, ValueError, RuntimeError, SyntaxError, OverflowError, MemoryError, FletException) as exc:
            if not view.closing:
                view.notify(f'Não foi possível importar a imagem: {exc}', 'warning')
        finally:
            view.lock(False)

    async def clipboard_source(self):
        clipboard = ft.Clipboard()
        try:
            data = await clipboard.get_image()
        except FletUnsupportedPlatformException:
            data = None
        if data:
            return import_image_bytes, data
        try:
            files = await clipboard.get_files()
        except FletUnsupportedPlatformException:
            files = []
        images = [Path(name) for name in files if Path(name).suffix.lower().lstrip('.') in IMAGE_EXTENSIONS]
        if len(images) > 1:
            raise ValueError('Copie uma imagem por vez para substituir a imagem do quadro ativo.')
        if images:
            return import_image, images[0]
        raise ValueError(self.view.keymap.describe('Copie uma imagem e use Colar imagem no quadro ativo', Action.PASTE))

    async def paste(self, e=None):
        view = self.view
        if not view.editable():
            return
        identifier = view.workspace.navigation.selected
        if identifier not in view.cards:
            view.notify('Selecione um quadro para colar a imagem.', 'warning')
            return
        if not next(frame for frame in view.board.frames if frame.id == identifier).node_type.image:
            view.notify('Selecione um quadro da cena para colar a imagem.', 'warning')
            return
        # O destino é capturado antes da leitura: uma troca de seleção não pode
        # direcionar a imagem para outro quadro durante a importação.
        view.properties.end_adjust()
        workspace = view.workspace
        if workspace.drag:
            workspace.cancel_drag(workspace.drag.identifier)
        workspace.box_selection.cancel()
        workspace.links.cancel()
        if workspace.links.cut_points:
            workspace.links.cancel_cut()
        view.lock(True)
        try:
            importer, source = await self.clipboard_source()
            name, data = await asyncio.to_thread(importer, source, view.store)
            if view.closing or identifier not in view.cards:
                return
            view.thumbnails[name] = data
            view.changed(view.board.change(identifier, image=name, crop_x=0, crop_y=0))
            view.refresh()
            view.page.update(view.content)
            if await view.persist():
                view.notify('Imagem colada no quadro ativo. Arraste sobre ela para enquadrar.', 'success')
        except (OSError, ValueError, RuntimeError, FletException) as exc:
            if not view.closing:
                view.notify(f'Não foi possível colar: {exc}', 'warning')
        finally:
            view.lock(False)
