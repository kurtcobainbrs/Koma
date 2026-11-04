"""Coordena cards, seletores e salvamento; imagens e PDF trabalham fora da interface."""

import asyncio
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import flet as ft

from koma.ui.design import CONTROL_HEIGHT, MUTED, dialog, input_style
from koma.paths import initial_directory
from koma.ui.operation_feedback import OperationFeedback
from koma.ui.typography import TEXT_BODY, TEXT_SMALL
from koma.editor.card import StoryCard
from koma.editor.canvas import StoryboardCanvas
from koma.editor.geometry import GRID_STEP, group_delta, next_position, place_missing, make_insertion_space
from koma.documents.images import IMAGE_EXTENSIONS, import_image, load_thumbnails
from koma.editor.models import MAX_CARDS, Storyboard, StoryFrame
from koma.exports.pdf_export import export_pdf
from koma.editor import graph
from koma.editor.graph_actions import GraphActions
from koma.editor.history import StoryHistory
from koma.editor.models import StoryLink, StoryGroup
from koma.editor.properties import FrameProperties
from koma.editor.project_properties import ProjectProperties
from koma.editor.animatic import AnimaticPlayer
from koma.editor.image_input import StoryboardImageInput
from koma.editor.file_actions import StoryboardFiles
from koma.editor.editor_chrome import StoryboardChrome
from koma.editor.node_types import node_type
from koma.preferences import StoryboardPreferences
from koma.editor.shortcuts import default_keymap
from koma.editor.sequence_actions import SequenceActions
from koma.editor.sequences import remap_frame
from koma.editor.node_media_actions import NodeMediaActions
from koma.ui.image_source import trim_thumbnails
from koma.editor.node_media import with_image
from koma.editor.work_modes import WorkModes
from koma.ui.workspace_style import WORKSPACE_STYLE
from koma.ui.focus_requests import FocusRequests
from koma.ui.retained_container import RetainedColumn, retain_children

CARD_BUILD_BATCH = 32
from koma.ui.splitter import Splitter


class StoryboardView:
    def __init__(self, page, session, settings, *, on_session=None, on_state=None):
        self.page, self.session, self.settings = page, session, settings
        self.on_session = on_session
        self.on_state = on_state
        self.can_save_to = None
        self.can_accept_drop = lambda: True
        from koma.editor.external_drop import ExternalImageDrop
        self.external_drop = ExternalImageDrop(self)
        self.active = True
        self.keymap = settings.shortcuts
        self.store = session.store
        self.preferences = StoryboardPreferences(self)
        self.board = Storyboard()
        self.history = StoryHistory()
        self.graph = GraphActions(self)
        self.sequences = SequenceActions(self)
        self.node_media = NodeMediaActions(self)
        self.cards, self.thumbnails = {}, {}
        self.busy = self.closing = self.loaded = False
        self.focus = FocusRequests(page)
        self.load_error = ''
        self.revision = 0
        self.save_lock = asyncio.Lock()
        self.image_directory = ''
        self.title = ft.TextField(value=self.board.title, hint_text='Nome do storyboard', expand=True,
            max_length=200, counter=ft.Container(width=0, height=0), on_change=self.edit_title, **input_style())
        self.add = ft.OutlinedButton('Novo quadro', icon=ft.Icons.ADD, height=CONTROL_HEIGHT, on_click=self.add_frame)
        self.add_scene = ft.OutlinedButton('Node Principal', icon=ft.Icons.MOVIE_OUTLINED,
            height=CONTROL_HEIGHT, on_click=self.add_principal, tooltip='Início de uma cena · conecte os quadros à saída')
        self.import_button = ft.OutlinedButton('Importar imagens', icon=ft.Icons.ADD_PHOTO_ALTERNATE_OUTLINED,
            height=CONTROL_HEIGHT, on_click=self.pick_images)
        self.export_button = ft.FilledButton('Exportar PDF', icon=ft.Icons.PICTURE_AS_PDF_OUTLINED,
            height=CONTROL_HEIGHT, on_click=self.export)
        self.files = StoryboardFiles(self)
        self.player = AnimaticPlayer(self)
        self.play_button = ft.OutlinedButton('Animatic', icon=ft.Icons.PLAY_CIRCLE_OUTLINED,
            height=CONTROL_HEIGHT, on_click=self.player.open)
        self.count = ft.Text(size=TEXT_SMALL, color=MUTED)
        self.workspace = StoryboardCanvas(self)
        self.image_input = StoryboardImageInput(self)
        from koma.ui.reference_canvas import ReferenceCanvas
        self.references = ReferenceCanvas(self)
        self.project_properties = ProjectProperties(self)
        self.properties = FrameProperties(self)
        self.properties_splitter = Splitter(page, self.properties.content,
            minimum=WORKSPACE_STYLE.inspector_minimum, maximum=WORKSPACE_STYLE.inspector_maximum, reverse=True)
        self.empty = ft.Container(left=64, right=56, top=24, padding=16, content=ft.Column([
            ft.Icon(ft.Icons.VIEW_MODULE_OUTLINED, size=36, color=MUTED),
            ft.Text('Comece com um quadro vazio ou importe imagens.', size=TEXT_BODY, color=MUTED),
            ft.Text('Mova os quadros e conecte Saída → Entrada para definir a sequência.', size=TEXT_SMALL, color=MUTED),
            ft.Row([self.add, self.import_button], wrap=True,
                alignment=ft.MainAxisAlignment.CENTER, spacing=8, run_spacing=8),
            ft.Text('Selecione um quadro para editar título, duração e textos no painel de propriedades.',
                size=TEXT_SMALL, color=MUTED),
        ], tight=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8))
        self.canvas = self.workspace.content
        self.board_area = ft.Stack([self.canvas, self.empty, self.workspace.navigation.tools],
            expand=True, fit=ft.StackFit.EXPAND)
        self.order_button = ft.TextButton('Organizar fluxo', icon=ft.Icons.ACCOUNT_TREE_OUTLINED,
            height=CONTROL_HEIGHT, tooltip='Alinha as sequências conectadas, preservando sua ordem.',
            on_click=self.graph.organize)
        self.feedback = OperationFeedback('Abra o storyboard para carregar os quadros.', compact=True, page=page)
        self.retry_save = ft.TextButton('Tentar salvar novamente', icon=ft.Icons.SAVE_OUTLINED,
            height=CONTROL_HEIGHT, visible=False, on_click=self.retry_persist)
        self.feedback.add_notice(self.retry_save)
        self.feedback.add_notice(self.files.actions)
        self.chrome = StoryboardChrome(self)
        self.toolbar = self.chrome.toolbar
        self.work_modes = WorkModes(self)
        self.content = RetainedColumn(hold_updates=lambda: False, controls=[
            self.chrome.content,
            self.work_modes.content, self.chrome.status,
        ], expand=True, spacing=4, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        self.refresh()
        self.keymap.listeners.append(self.shortcuts_changed)

    @property
    def production(self):
        return self.sequences.index.production

    @property
    def edit_selection(self):
        if self.references.active:
            return self.references.selection
        return self.player.selection if self.player.opened else self.workspace.navigation.selection

    def field_focus(self, identifier, key, focused):
        nav = self.workspace.navigation
        if not self.player.opened:
            nav.field_focus(identifier, key, focused)
        elif focused:
            nav.editing_fields.add((identifier, key))
        else:
            nav.editing_fields.discard((identifier, key))

    def focus_editor(self):
        self.work_modes.focus()

    def shortcuts_changed(self):
        self.workspace.navigation.refresh_shortcuts()
        self.player.preview_navigation.configure()
        self.player.strip.configure_navigation()
        if self.player.opened:
            self.page.update(self.player.preview_navigation.content, self.player.layout.timeline)
        if self.references.secondary_pan:
            from koma.editor.shortcuts import Action
            self.references.secondary_pan.zoom_modifiers = list(self.keymap.bindings(Action.DRAG_ZOOM))
            if self.references.active:
                self.page.update(self.references.secondary_pan)
        self.chrome.refresh_shortcuts()
        self.chrome.sync()
        self.external_drop.sync()

    def notify(self, text, state='info'):
        self.feedback.set(text, state)
        if hasattr(self, 'chrome'):
            self.chrome.sync_status()
        if not self.closing and self.active:
            self.page.update(self.feedback.content)

    def lock(self, busy, *, update=True):
        self.busy = busy
        if not update:
            return
        if busy:
            self.feedback.set_state('working')
        elif self.feedback.state == 'working':
            self.feedback.set_state('info')
        self.toolbar.disabled = self.canvas.disabled = self.workspace.controls.disabled = self.order_button.disabled = self.workspace.navigation.tools.disabled = busy or bool(self.load_error)
        self.workspace.navigation.selection_bar.disabled = busy or bool(self.load_error)
        self.graph.menu.disabled = busy or bool(self.load_error)
        self.files.menu.disabled = busy
        self.properties.content.disabled = busy or bool(self.load_error)
        for card in self.cards.values():
            card.viewport.layout()
        self.graph.sync_history()
        self.chrome.sync()
        self.chrome.lock(busy)
        self.external_drop.sync()
        self.workspace.secondary_pointer.sync()
        if not self.closing and self.active:
            self.page.update(self.content)

    async def activate(self):
        if not hasattr(self, 'preference_bindings'):
            from koma.editor.preference_bindings import PreferenceBindings
            self.preference_bindings = PreferenceBindings(self)
        self.focus.resume()
        if self.closing or self.busy:
            return
        if self.loaded:
            self.preference_bindings.apply()
            if not self.load_error:
                if self.references.active:
                    self.references.sync()
                    self.references.focus()
                    self.references.restore()
                elif self.player.suspended:
                    self.player.resume()
                else:
                    await self.workspace.resume()
            return
        self.lock(True)
        try:
            await self.preferences.load()
            self.preference_bindings.apply()
            self.player.show_subtitles.selected = self.preferences.options.show_subtitles
            self.files.include_subtitles = self.preferences.options.include_subtitles
            board = self.session.board
            await self.workspace.camera_memory.load()
            thumbnails = await asyncio.to_thread(load_thumbnails, board, self.store)
            if self.closing:
                return
            self.board, self.thumbnails = place_missing(graph.ordered(board)), thumbnails
            self.title.value = board.title
            # Loading owns the busy state. Yield between bounded UI batches so
            # other application events are not starved by a large document.
            for index, frame in enumerate(self.board.frames, 1):
                card = self.cards[frame.id] = StoryCard(self, frame)
                card.sync(frame)
                if index % CARD_BUILD_BATCH == 0:
                    await asyncio.sleep(0)
                    if self.closing:
                        return
            self.loaded = True
            self.refresh()
            self.notify('Conecte Saída → Entrada para ordenar o fluxo. Arraste um quadro sobre um fio para inseri-lo. Use Cancelar para interromper.')
        except (OSError, ValueError) as exc:
            self.load_error = str(exc)
            self.loaded = True
            self.notify(f'{exc} O documento existente foi preservado.', 'error')
        finally:
            self.lock(False)

    def snapshot_presentations(self):
        return {identifier: card.viewport.presentation_key for identifier, card in self.cards.items()}

    def publish(self, previous=None):
        """Publish document/layout changes while retaining unchanged image/vector bodies."""
        previous = previous or {}
        stable = [card.viewport.content for identifier, card in self.cards.items()
            if identifier in previous and previous[identifier] == card.viewport.presentation_key]
        with retain_children(*stable):
            self.page.update(self.content)

    def refresh(self):
        self.references.sync()
        trim_thumbnails(self)
        ids = {frame.id for frame in self.board.frames}
        self.cards = {key: card for key, card in self.cards.items() if key in ids}
        self.workspace.scope.sync()
        number = 0
        for frame in self.board.frames:
            if frame.node_type.timed:
                number += 1
            if frame.id not in self.cards:
                self.cards[frame.id] = StoryCard(self, frame)
            self.cards[frame.id].sync(frame)
            self.cards[frame.id].content.visible = frame.id in self.workspace.scope.visible
            self.cards[frame.id].number.value = (self.production.code(frame.id) or '—'
                if frame.node_type.timed else frame.node_type.header)
        self.graph.sync_history()
        self.workspace.refresh()
        self.properties.sync()
        self.project_properties.sync()
        scenes = sum(frame.node_type.starts_scene for frame in self.board.frames)
        sequences = sum(frame.node_type.contains_frames for frame in self.board.frames)
        parts = [f'{number} quadros', f'{scenes} cenas', f'{len(self.board.links)} ligações']
        if sequences:
            parts.insert(1, f'{sequences} ' + ('sequência' if sequences == 1 else 'sequências'))
        self.count.value = ' · '.join(parts)
        self.empty.visible = not self.board.frames
        self.external_drop.sync()
        self.export_button.disabled = not number
        self.play_button.disabled = not self.board.frames
        self.chrome.sync()
        if self.active and self.loaded and self.board.frames and not self.workspace.initial_view_done:
            self.page.run_task(self.workspace.ensure_initial_view)
        if hasattr(self, 'work_modes'):
            self.player.document_changed()

    def editable(self):
        return self.active and self.loaded and not self.busy and not self.closing and not self.load_error

    async def retry_persist(self, e):
        await self.persist()

    async def pick_images(self, e):
        await self.pick_image()

    def changed(self, board, coalesce_key=None, *, label=None):
        board = graph.ordered(board)
        if board == self.board:
            return
        from koma.editor.history_labels import change_label
        self.history.record(self.board, coalesce_key, label or change_label(self.board, board))
        self.board = board
        self.revision += 1
        self.graph.sync_history()
        if self.loaded and not self.closing:
            self.chrome.sync()
            self.page.update(self.chrome.content)

    @property
    def document_label(self):
        return (self.board.title or 'Sem título') + (' *' if self.dirty else '')

    @property
    def dirty(self):
        return self.session.saved_board is None or self.board != self.session.saved_board

    async def persist(self):
        """Recuperação local; nunca sobrescreve o arquivo escolhido pelo usuário."""
        async with self.save_lock:
            if self.load_error:
                return False
            board = self.board
            self.session.board = board
            try:
                config = self.settings.configuration
                options = config.values['system']
                await asyncio.to_thread(self.session.recover, board,
                    backup_interval=options['interval'] if config.path.exists() else 0,
                    backup_count=options['backups'])
                self.retry_save.visible = False
                self.chrome.sync()
                if not self.closing and self.active:
                    self.page.update(self.chrome.content)
                return True
            except (OSError, ValueError) as exc:
                self.retry_save.visible = True
                self.notify(f'Não foi possível atualizar a recuperação local: {exc}', 'error')
                return False

    async def switch_session(self, session):
        if self.on_session is None:
            raise RuntimeError('O aplicativo não forneceu o controlador de documentos.')
        await self.on_session(session)

    async def edit_title(self, e):
        if self.editable():
            self.changed(replace(self.board, title=self.title.value or ''), 'title')
            await self.persist()

    async def edit_frame(self, identifier, key, value):
        if self.editable() and any(frame.id == identifier for frame in self.board.frames):
            self.changed(self.board.change(identifier, **{key: value or ''}), (identifier, key))
            await self.persist()

    async def set_frame_properties(self, identifier, coalesce_key=None, *, label=None, **values):
        await self.set_frames_properties({identifier: values}, coalesce_key, label=label)

    async def set_frames_properties(self, changes, coalesce_key=None, *, label=None):
        """One model/history/save operation, regardless of the number of affected nodes."""
        if not self.editable() or not changes or not changes.keys() <= self.cards.keys():
            return
        try:
            board = replace(self.board, frames=tuple(replace(frame, **changes[frame.id])
                if frame.id in changes else frame for frame in self.board.frames))
            self.changed(board, coalesce_key, label=label)
            for frame in self.board.frames:
                if frame.id in changes:
                    self.cards[frame.id].sync(frame)
                    self.sequences.sync_ancestors(frame.id)
            self.page.update(*(self.cards[key].content for key in changes))
            if self.properties.sync_path():
                self.page.update(self.properties.scene_info)
            self.player.document_changed()
            await self.persist()
        except ValueError as exc:
            self.notify(str(exc), 'warning')

    def node_handler(self, kind):
        node_type(kind)
        async def add(e=None):
            await self.add_node(kind)
        return add

    async def add_frame(self, e=None):
        await self.add_node('frame')

    async def add_principal(self, e=None):
        await self.add_node('main')

    async def add_node(self, kind, *, position=None):
        if not self.editable():
            return
        spec = node_type(kind)
        if spec.starts_scene and self.workspace.scope.active is not None:
            self.notify('Crie cenas no canvas principal.', 'warning')
            return
        if spec.contains_frames:
            await self.sequences.create(spec=spec, position=position)
            return
        if len(self.board.frames) >= MAX_CARDS:
            self.notify(f'O storyboard aceita até {MAX_CARDS} nodes.', 'warning')
            return
        x, y = self.workspace.scope.next_position() if position is None else position
        number = sum(frame.kind == kind for frame in self.board.frames) + 1
        title = f'{spec.title_prefix} {number:02d}' if spec.title_prefix else ''
        frame = StoryFrame(kind=kind, title=title, x=x, y=y)
        self.changed(self.workspace.scope.attach_new(replace(self.board, frames=(*self.board.frames, frame)), (frame.id,)))
        self.refresh()
        if spec.starts_scene:
            self.workspace.navigation.select_node(frame.id, focus=True)
        self.page.update(self.content)
        await self.persist()

    async def toggle_muted(self, identifiers=None):
        if not self.editable():
            return
        identifiers = self.workspace.navigation.selection.ids if identifiers is None else identifiers
        identifiers = self.sequences.index.closure(identifiers)
        targets = [frame for frame in self.board.frames if frame.id in identifiers and not frame.node_type.contains_frames]
        if not targets:
            return
        identifiers = {frame.id for frame in targets}
        muted = not all(frame.muted for frame in targets)
        await self.graph.commit(replace(self.board, frames=tuple(
            replace(frame, muted=muted) if frame.id in identifiers else frame for frame in self.board.frames)))

    async def duplicate(self, identifier):
        # Botão e atalho usam a mesma cópia próxima da origem, sem procurar um
        # slot vazio na grade global do canvas.
        await self.duplicate_frames({identifier})

    def confirm_remove(self, identifier):
        self.confirm_remove_frames({identifier})

    async def duplicate_frames(self, identifiers):
        if not self.editable():
            return
        identifiers = self.sequences.index.closure(identifiers)
        originals = [frame for frame in self.board.frames if frame.id in identifiers]
        if not originals:
            return
        if len(self.board.frames) + len(originals) > MAX_CARDS:
            self.notify(f'O storyboard aceita até {MAX_CARDS} quadros.', 'warning')
            return
        positions = {frame.id: (frame.x, frame.y) for frame in originals}
        dx, dy = group_delta(positions, GRID_STEP * 2, GRID_STEP * 2,
                            anchor=(originals[0].x, originals[0].y))
        mapping = {frame.id: uuid4().hex for frame in originals}
        roots = set(self.sequences.index.roots(identifiers))
        copies = tuple(remap_frame(frame, mapping, x=frame.x + (dx if frame.id in roots else 0),
            y=frame.y + (dy if frame.id in roots else 0)) for frame in originals)
        frames = list(self.board.frames)
        index = max(i for i, frame in enumerate(frames) if frame.id in identifiers) + 1
        frames[index:index] = copies
        links = tuple(StoryLink(mapping[edge.source], mapping[edge.target]) for edge in self.board.links
                      if edge.source in mapping and edge.target in mapping)
        groups = tuple(StoryGroup(title=group.title, members=tuple(mapping[key] for key in group.members))
                       for group in self.board.groups if set(group.members) <= mapping.keys())
        self.changed(self.workspace.scope.attach_new(replace(self.board, frames=tuple(frames),
            links=(*self.board.links, *links), groups=(*self.board.groups, *groups)), (frame.id for frame in copies)))
        self.refresh()
        self.workspace.navigation.apply_selection({frame.id for frame in copies}, copies[0].id)
        self.page.update(self.content)
        self.workspace.navigation.focus_keyboard()
        await self.persist()

    def confirm_remove_frames(self, identifiers, preserve_flow=False):
        if self.settings.configuration.values['confirmations']['delete']:
            async def confirm():
                board = self.board
                choice = await self.files.choose('Excluir nodes?', 'A exclusão pode ser desfeita.',
                    [('cancel', 'Cancelar'), ('delete', 'Excluir')], confirm='delete')
                if choice == 'delete' and self.board is board:
                    self.remove_confirmed_frames(identifiers, preserve_flow)
            self.page.run_task(confirm)
        else:
            self.remove_confirmed_frames(identifiers, preserve_flow)

    def remove_confirmed_frames(self, identifiers, preserve_flow=False):
        if not self.editable():
            return
        targets = frozenset(frame.id for frame in self.board.frames if frame.id in identifiers)
        if not targets:
            return
        self.workspace.links.cancel()
        self.changed(graph.remove_frames(self.board, targets, reconnect=preserve_flow))
        self.refresh()
        self.page.update(self.content)
        self.page.run_task(self.persist)

    async def move(self, source, target=None):
        if not self.editable():
            return
        if self.board.links:
            self.notify('A ordem é definida pelas conexões. Desconecte os quadros para mudar a sequência.', 'warning')
            return
        try:
            updated = self.board.move(source, target)
            if updated == self.board:
                return
            self.changed(updated)
            self.refresh()
            self.page.update(self.content)
            await self.persist()
        except ValueError as exc:
            self.notify(str(exc), 'error')

    async def position_frame(self, identifier, x, y):
        await self.position_frames({identifier: (x, y)})

    async def position_frames(self, positions, insert_flow=False, detach_flow=False):
        if not self.editable():
            return
        placed = positions
        updated = replace(self.board, frames=tuple(replace(frame, x=placed[frame.id][0], y=placed[frame.id][1])
            if frame.id in placed else frame for frame in self.board.frames))
        candidate = self.workspace.links.candidate
        if detach_flow:
            updated = graph.detach(updated, self.sequences.index.closure(positions))
        elif (insert_flow and len(positions) == 1 and candidate
                and not any(key in (edge.source, edge.target) for key in positions for edge in self.board.links)):
            try:
                identifier = next(iter(positions))
                inserted = graph.insert(updated, identifier, candidate)
                updated = make_insertion_space(inserted, identifier, candidate, self.workspace.node_heights)
            except ValueError as exc:
                self.notify(str(exc), 'warning')
        self.workspace.links.candidate = None
        self.changed(updated)
        self.refresh()
        self.page.update(self.canvas)
        await self.workspace.compensate_origin()
        await self.persist()

    async def shift_frame(self, identifier, delta):
        if not self.editable():
            return
        index = next((i for i, frame in enumerate(self.board.frames) if frame.id == identifier), None)
        if index is None or not 0 <= index + delta < len(self.board.frames):
            return
        target = self.board.frames[index - 1].id if delta < 0 else (
            self.board.frames[index + 2].id if index + 2 < len(self.board.frames) else None)
        await self.move(identifier, target)

    async def order_by_position(self, e=None):
        if not self.editable():
            return
        if self.board.links:
            self.notify('A numeração acompanha as conexões do fluxo.', 'info')
            return
        frames = tuple(sorted(self.board.frames, key=lambda frame: (round(frame.y / GRID_STEP), frame.x)))
        self.changed(replace(self.board, frames=frames))
        self.refresh()
        self.page.update(self.content)
        await self.persist()

    async def pick_image(self, identifier=None):
        if self.references.active:
            await self.references.actions.pick()
            return
        if not self.editable():
            return
        self.lock(True)
        try:
            root = str(self.session.path.parent) if self.session.path else ''
            directory = await asyncio.to_thread(initial_directory,
                self.settings.configuration.values['files']['import_folder'] or self.image_directory, root)
            selected = await ft.FilePicker().pick_files(dialog_title='Imagens do storyboard',
                allow_multiple=identifier is None, file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=IMAGE_EXTENSIONS, initial_directory=directory)
            if selected and not self.closing:
                await self.import_paths([Path(item.path) for item in selected if item.path], identifier)
        except (OSError, ValueError, RuntimeError) as exc:
            self.notify(str(exc), 'error')
        finally:
            self.lock(False)

    async def import_paths(self, paths, identifier=None):
        """Importa sequencialmente para limitar memória; uma imagem inválida não descarta as demais."""
        failures = []
        imported = 0
        for source in paths:
            if self.closing:
                break
            if identifier is None and len(self.board.frames) >= MAX_CARDS:
                failures.append(f'Limite de {MAX_CARDS} quadros atingido.')
                break
            try:
                self.notify(f'Importando {source.name}…', 'working')
                name, data = await asyncio.to_thread(import_image, source, self.store)
                self.thumbnails[name] = data
                if identifier:
                    original = self.node_media.target(identifier)
                    updated = with_image(original, name, source.name)
                    self.changed(self.board.change(identifier, media=updated.media, active_media_id=updated.active_media_id))
                    self.cards[identifier].set_image(name)
                else:
                    x, y = self.workspace.scope.next_position()
                    frame = with_image(StoryFrame(title=source.stem, x=x, y=y), name, source.name)
                    self.changed(self.workspace.scope.attach_new(replace(self.board, frames=(*self.board.frames, frame)), (frame.id,)))
                self.image_directory = str(source.parent)
                imported += 1
            except (OSError, ValueError) as exc:
                failures.append(str(exc))
        self.refresh()
        if not self.closing:
            self.page.update(self.content)
        saved = await self.persist()
        if saved:
            self.notify(f'{imported} imagens importadas.' + (' ' + ' '.join(failures) if failures else ''),
                        'warning' if failures else 'success')

    async def export(self, e=None):
        if not self.editable() or not self.board.frames:
            return
        from koma.ui.pdf_export_panel import PdfExportPanel
        PdfExportPanel(self).open()

    async def export_pdf_file(self, *, options=None, preferences=None):
        if not self.editable() or not self.board.frames:
            return
        self.lock(True)
        try:
            root = str(self.session.path.parent) if self.session.path else ''
            directory = await asyncio.to_thread(initial_directory,
                self.settings.configuration.values['files']['export_folder'], root)
            # O nome informado ao seletor não pode conter separadores de caminho.
            name = ''.join(c for c in self.board.title if c not in '<>:"/\\|?*').strip(' .') or 'storyboard'
            destination = await ft.FilePicker().save_file(dialog_title='Exportar storyboard em PDF',
                file_name=f'{name}.pdf', initial_directory=directory,
                file_type=ft.FilePickerFileType.CUSTOM, allowed_extensions=['pdf'])
            if destination and not self.closing:
                self.notify('Gerando PDF…', 'working')
                saved = await asyncio.to_thread(export_pdf, self.board, self.store, Path(destination),
                    options=options, preferences=preferences or self.settings.configuration.values)
                self.notify(f'PDF exportado: {saved}', 'success')
        except (OSError, ValueError, RuntimeError) as exc:
            self.notify(f'Não foi possível exportar: {exc}', 'error')
        finally:
            self.lock(False)

    async def deactivate(self):
        """Suspende gestos/player ao sair da aba, preservando documento e histórico."""
        self.focus.suspend()
        if self.references.gesture:
            self.references.cancel()
        self.references.suspend_camera()
        self.workspace.camera_memory.remember()
        self.workspace.cancel_gestures()
        self.properties.end_adjust()
        self.node_media.close_editor()
        if self.player.opened:
            self.player.suspend()
        else:
            self.player.dismissed()
        nav = self.workspace.navigation
        nav.reset_keys()
        nav.editing_fields.clear()
        await self.preferences.flush()
        await self.workspace.camera_memory.flush()
        self.active = False

    async def shutdown(self):
        self.references.suspend_camera()
        if hasattr(self, 'preference_bindings'):
            self.preference_bindings.close()
        self.focus.suspend()
        self.node_media.close_editor()
        self.workspace.measurements.cancel()
        if self.shortcuts_changed in self.keymap.listeners:
            self.keymap.listeners.remove(self.shortcuts_changed)
        self.workspace.grab.cancel(update=False)
        if self.workspace.drag:
            self.workspace.cancel_drag(self.workspace.drag.identifier)
        self.workspace.box_selection.cancel()
        self.workspace.box_zoom.cancel()
        self.workspace.links.cancel()
        self.workspace.links.cancel_cut()
        self.player.dismissed()
        self.properties.end_adjust()
        self.workspace.cancel_camera_transition()
        await self.preferences.flush()
        await self.workspace.camera_memory.flush()
        await self.files.shutdown()
        await self.player.media.shutdown()
        await self.player.video_preview.shutdown()
        await asyncio.to_thread(self.player.audio_transport.close)
        # Aguarda qualquer gravação de recuperação antes de limpar a sessão.
        async with self.save_lock:
            self.closing = True
