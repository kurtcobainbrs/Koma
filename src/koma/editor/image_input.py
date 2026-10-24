"""Entrada de imagens no quadro ativo, isolada da edição e da geometria."""

import asyncio
from pathlib import Path

import flet as ft
from koma.editor.shortcuts import Action
from flet.controls.exceptions import FletException, FletUnsupportedPlatformException

from koma.documents.images import IMAGE_EXTENSIONS, import_image, import_image_bytes


class StoryboardImageInput:
    def __init__(self, view):
        self.view = view

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
