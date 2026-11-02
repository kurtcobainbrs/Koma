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
from koma.editor.node_media import with_image
from koma.editor.canvas_position import insertion_position


class StoryboardImageInput:
    def __init__(self, view):
        self.view = view

    async def drop(self, paths, position, identifier=None):
        """Destino capturado no drop, validado antes de qualquer alteração."""
        view = self.view
        if not view.editable():
            return
        from koma.editor.node_media import VIDEO_EXTENSIONS
        if any(Path(path).suffix.lower().lstrip('.') in VIDEO_EXTENSIONS for path in paths):
            await view.node_media.import_paths(identifier, paths, position=position)
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
                changed = with_image(frame, name, source.name)
                updated = view.board.change(identifier, media=changed.media, active_media_id=changed.active_media_id)
            else:
                x, y = (coordinate(n, snap=view.workspace.snap_enabled) for n in position)
                frame = with_image(StoryFrame(title=source.stem, x=x, y=y), name, source.name)
                updated = view.workspace.scope.attach_new(replace(view.board, frames=(*view.board.frames, frame)), (frame.id,))
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
            raise ValueError('Copie uma imagem por vez.')
        if images:
            return import_image, images[0]
        raise ValueError(self.view.keymap.describe('Copie uma imagem e use Colar', Action.PASTE))

    async def paste(self, e=None):
        view = self.view
        if not view.editable():
            return
        identifier = view.edit_selection.active
        frame = next((item for item in view.board.frames if item.id == identifier), None)
        if frame is not None and not frame.node_type.image:
            view.notify('Selecione um quadro da cena para colar a imagem.', 'warning')
            return
        if frame is None and len(view.board.frames) >= MAX_CARDS:
            view.notify(f'Limite de {MAX_CARDS} quadros atingido.', 'warning')
            return
        identifier = frame.id if frame else None
        board, session = view.board, view.session
        position = insertion_position(view.workspace)
        scope = view.workspace.scope.active
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
            if view.closing or not view.active or view.session is not session or view.board is not board or workspace.scope.active != scope:
                return
            view.thumbnails[name] = data
            label = source.name if isinstance(source, Path) else 'Colada'
            if identifier is not None:
                changed = with_image(frame, name, label)
                updated = board.change(identifier, media=changed.media, active_media_id=changed.active_media_id)
            else:
                step = view.settings.configuration.values['canvas']['spacing']
                x, y = (coordinate(round(value / step) * step if workspace.snap_enabled else value, snap=False) for value in position)
                changed = with_image(StoryFrame(title=source.stem if isinstance(source, Path) else '', x=x, y=y), name, label)
                identifier = changed.id
                updated = workspace.scope.attach_new(replace(board, frames=(*board.frames, changed)), (identifier,))
            updated.validate()
            view.changed(updated, label='Colar imagem' if frame else 'Colar imagem como quadro')
            view.refresh()
            workspace.navigation.apply_selection({identifier}, identifier)
            view.page.update(view.content)
            if await view.persist():
                view.notify('Imagem adicionada ao quadro.' if frame else 'Quadro criado com a imagem.', 'success')
        except (OSError, ValueError, RuntimeError, FletException) as exc:
            if not view.closing:
                view.notify(f'Não foi possível colar: {exc}', 'warning')
        finally:
            view.lock(False)
