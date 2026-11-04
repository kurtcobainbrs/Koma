"""Transactional media imports and selection; never change a node's timing."""
import asyncio
from dataclasses import replace
from pathlib import Path
import flet as ft
from koma.documents.images import IMAGE_EXTENSIONS, import_image, load_thumbnails
from koma.documents.videos import import_video
from koma.editor.node_media import NodeMedia, VIDEO_EXTENSIONS, MAX_MEDIA_ITEMS
from koma.editor.models import Storyboard, StoryFrame, MAX_CARDS
from koma.editor.geometry import coordinate, next_position

MEDIA_EXTENSIONS = (*IMAGE_EXTENSIONS, *VIDEO_EXTENSIONS)


class NodeMediaActions:
    def __init__(self, view):
        self.view = view
        self.editor = None

    def target(self, identifier):
        return next((frame for frame in self.view.board.frames if frame.id == identifier), None)

    def ready(self):
        view = self.view
        if not view.editable() or view.player.editing:
            return False
        view.properties.end_adjust()
        if view.workspace.grab.active:
            view.workspace.grab.cancel()
        elif view.workspace.drag:
            view.workspace.cancel_drag(view.workspace.drag.identifier)
        return True

    async def pick(self, identifier):
        if not self.ready():
            return
        session = self.view.session
        files = await ft.FilePicker().pick_files(dialog_title='Adicionar mídias', allow_multiple=True,
            file_type=ft.FilePickerFileType.CUSTOM, allowed_extensions=list(MEDIA_EXTENSIONS),
            initial_directory=await self.view.files.initial())
        if files and self.view.session is session:
            await self.import_paths(identifier, [Path(item.path) for item in files if item.path])

    async def import_paths(self, identifier, paths, *, position=None):
        view = self.view
        creating = identifier is None
        frame = self.target(identifier) if not creating else StoryFrame(
            **dict(zip(('x', 'y'), (coordinate(value, snap=view.workspace.snap_enabled)
                for value in (position or view.workspace.scope.next_position())))))
        if not frame or not frame.node_type.image or not self.ready():
            return
        if creating and len(view.board.frames) >= MAX_CARDS:
            view.notify(f'Limite de {MAX_CARDS} nodes atingido.', 'warning')
            return
        board, session, revision, store = view.board, view.session, view.revision, view.store
        added, thumbnails, errors = [], {}, []
        view.lock(True)
        try:
            for source in paths:
                source = Path(source)
                if sum(len(node.media) for node in board.frames) + len(added) >= MAX_MEDIA_ITEMS:
                    raise ValueError('O projeto atingiu o limite de itens de mídia.')
                view.notify(f'Importando {source.name}…', 'working')
                try:
                    if source.suffix.lower().lstrip('.') in VIDEO_EXTENSIONS:
                        item, data = await asyncio.to_thread(import_video, source, store)
                    else:
                        name, data = await asyncio.to_thread(import_image, source, store)
                        item = NodeMedia(asset=name, label=source.name[:200])
                    added.append(item)
                    thumbnails = {item.image: data}
                except (OSError, ValueError, RuntimeError) as exc:
                    errors.append(str(exc))
            if (not added or view.closing or not view.active or view.session is not session
                    or view.revision != revision):
                return
            if creating:
                frame = replace(frame, title=Path(paths[0]).stem[:200], media=tuple(added), active_media_id=added[-1].id)
                updated = view.workspace.scope.attach_new(replace(board, frames=(*board.frames, frame)), (frame.id,))
                identifier = frame.id
            else:
                updated = board.change(identifier, media=(*frame.media, *added), active_media_id=added[-1].id)
            view.thumbnails.update(thumbnails)
            view.changed(updated, label='Adicionar mídias')
            imported = len(added)
            added.clear()  # Assets now belong to the document and undo history.
            self.refresh(identifier)
            if creating:
                view.workspace.navigation.apply_selection({identifier}, identifier)
            await view.persist()
            view.notify(f'{imported} mídias adicionadas.', 'success')
        except (OSError, ValueError, RuntimeError) as exc:
            errors.append(str(exc))
        finally:
            for item in added:
                (getattr(store, item.folder) / item.asset).unlink(missing_ok=True)
                if item.poster:
                    (store.images / item.poster).unlink(missing_ok=True)
                (store.thumbnails / item.image).unlink(missing_ok=True)
            view.lock(False)
            if errors and not view.closing:
                view.notify(' '.join(errors), 'warning')

    async def activate(self, identifier, media_id):
        frame = self.target(identifier)
        if not frame or not self.ready() or frame.active_media_id == media_id:
            return
        if not any(item.id == media_id for item in frame.media):
            return
        await self.commit(frame, frame.media, media_id, 'Trocar mídia')

    async def remove(self, identifier, media_id):
        frame = self.target(identifier)
        if not frame or not self.ready():
            return
        entries = tuple(item for item in frame.media if item.id != media_id)
        active = frame.active_media_id if any(item.id == frame.active_media_id for item in entries) else (entries[0].id if entries else '')
        await self.commit(frame, entries, active, 'Remover mídia')

    async def flip(self, identifier, axis):
        frame = self.target(identifier)
        if not frame or not frame.active_media or not self.ready():
            return
        attribute = {'horizontal': 'flip_x', 'vertical': 'flip_y'}[axis]
        active = frame.active_media
        transformed = replace(active, transform=replace(active.transform,
            **{attribute: not getattr(active.transform, attribute)}))
        entries = tuple(transformed if item.id == active.id else item for item in frame.media)
        await self.commit(frame, entries, frame.active_media_id, 'Inverter mídia')

    async def commit(self, frame, entries, active, label):
        view = self.view
        board, session = view.board, view.session
        updated = replace(frame, media=entries, active_media_id=active)
        try:
            if updated.image and updated.image not in view.thumbnails:
                data = await asyncio.to_thread(load_thumbnails, Storyboard(frames=(updated,)), view.store)
                if view.board is not board or view.session is not session or not view.editable():
                    return
                view.thumbnails.update(data)
            await view.set_frame_properties(frame.id, media=entries, active_media_id=active, label=label)
            self.refresh(frame.id)
        except (OSError, ValueError, RuntimeError) as exc:
            view.notify(f'Não foi possível alterar a mídia: {exc}', 'warning')

    def refresh(self, identifier):
        view = self.view
        from koma.ui.image_source import trim_thumbnails
        trim_thumbnails(view)
        frame = self.target(identifier)
        if frame is None:
            return
        if identifier not in view.cards:
            view.refresh()
            view.page.update(view.content)
        view.cards[identifier].sync(frame)
        view.properties.sync()
        view.page.update(view.cards[identifier].content, view.properties.content)
        if self.editor is not None:
            self.editor.sync(self.target(identifier))
            view.page.update(self.editor.content)
        if view.player.opened:
            view.player.document_changed()

    def open_editor(self, identifier):
        from koma.ui.node_media_list import MediaEditor
        if self.target(identifier) is not None and self.ready():
            self.view.player.playing = False
            self.view.player.render_position()
            MediaEditor(self.view, identifier).open()

    def close_editor(self):
        if self.editor is not None:
            self.editor.close()
