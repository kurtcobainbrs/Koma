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
from koma.ui.components import list_surface
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
        self.cards, self.thumbnails = {}, {}
        self.busy = self.closing = self.loaded = False
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
        self.project_properties = ProjectProperties(self)
        self.properties = FrameProperties(self)
        self.properties_splitter = Splitter(page, self.properties.content, minimum=240, maximum=600, reverse=True)
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
        self.content = ft.Column([
            self.chrome.content,
            ft.Row([list_surface([self.board_area]), self.properties_splitter.content,
                self.properties.content, self.properties.reopen_rail], expand=True, spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.STRETCH), self.chrome.status,
        ], expand=True, spacing=4, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        self.refresh()
        self.keymap.listeners.append(self.shortcuts_changed)

    def shortcuts_changed(self):
        self.workspace.navigation.refresh_shortcuts()
        self.chrome.refresh_shortcuts()
        self.chrome.sync()
        self.external_drop.sync()

    def notify(self, text, state='info'):
        self.feedback.set(text, state)
        if hasattr(self, 'chrome'):
            self.chrome.sync_status()
        if not self.closing and self.active:
            self.page.update(self.feedback.content)

    def lock(self, busy):
        self.busy = busy
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
        if self.closing or self.busy:
            return
        if self.loaded:
            if not self.load_error:
                await self.workspace.resume()
            return
        self.lock(True)
        try:
            await self.preferences.load()
            self.player.show_subtitles.selected = self.preferences.options.show_subtitles
            self.files.include_subtitles = self.preferences.options.include_subtitles
            board = self.session.board
            await self.workspace.camera_memory.load()
            thumbnails = await asyncio.to_thread(load_thumbnails, board, self.store)
            if self.closing:
                return
            self.board, self.thumbnails = place_missing(graph.ordered(board)), thumbnails
            self.title.value = board.title
            self.loaded = True
            self.refresh()
            self.notify('Conecte Saída → Entrada para ordenar o fluxo. Arraste um quadro sobre um fio para inseri-lo. Use Cancelar para interromper.')
        except (OSError, ValueError) as exc:
            self.load_error = str(exc)
            self.loaded = True
            self.notify(f'{exc} O documento existente foi preservado.', 'error')
        finally:
            self.lock(False)

    def refresh(self):
        ids = {frame.id for frame in self.board.frames}
        self.cards = {key: card for key, card in self.cards.items() if key in ids}
        number = 0
        for frame in self.board.frames:
            if frame.node_type.timed:
                number += 1
            if frame.id not in self.cards:
                self.cards[frame.id] = StoryCard(self, frame)
            self.cards[frame.id].sync(frame)
            self.cards[frame.id].number.value = (f'{frame.node_type.header} {number:02d}'
                if frame.node_type.timed else frame.node_type.header)
        self.graph.sync_history()
        self.workspace.refresh()
        self.properties.sync()
        self.project_properties.sync()
        scenes = sum(frame.node_type.starts_scene for frame in self.board.frames)
        self.count.value = f'{number} quadros · {scenes} cenas · {len(self.board.links)} ligações'
        self.empty.visible = not self.board.frames
        self.external_drop.sync()
        self.export_button.disabled = not number
        self.play_button.disabled = not self.board.frames
        self.chrome.sync()
        if self.active and self.loaded and self.board.frames and not self.workspace.initial_view_done:
            self.page.run_task(self.workspace.ensure_initial_view)

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
                await asyncio.to_thread(self.session.recover, board)
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

    async def set_frame_properties(self, identifier, coalesce_key=None, **values):
        if not self.editable() or identifier not in self.cards:
            return
        try:
            self.changed(self.board.change(identifier, **values), coalesce_key)
            frame = next(frame for frame in self.board.frames if frame.id == identifier)
            self.cards[identifier].sync(frame)
            self.page.update(self.cards[identifier].content)
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
        if len(self.board.frames) >= MAX_CARDS:
            self.notify(f'O storyboard aceita até {MAX_CARDS} nodes.', 'warning')
            return
        x, y = next_position(self.board.frames) if position is None else position
        number = sum(frame.kind == kind for frame in self.board.frames) + 1
        title = f'{spec.title_prefix} {number:02d}' if spec.title_prefix else ''
        frame = StoryFrame(kind=kind, title=title, x=x, y=y)
        self.changed(replace(self.board, frames=(*self.board.frames, frame)))
        self.refresh()
        if spec.starts_scene:
            self.workspace.navigation.select_node(frame.id, focus=True)
        self.page.update(self.content)
        await self.persist()

    async def toggle_muted(self, identifiers=None):
        if not self.editable():
            return
        identifiers = self.workspace.navigation.selection.ids if identifiers is None else identifiers
        targets = [frame for frame in self.board.frames if frame.id in identifiers]
        if not targets:
            return
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
        originals = [frame for frame in self.board.frames if frame.id in identifiers]
        if not originals:
            return
        if len(self.board.frames) + len(originals) > MAX_CARDS:
            self.notify(f'O storyboard aceita até {MAX_CARDS} quadros.', 'warning')
            return
        positions = {frame.id: (frame.x, frame.y) for frame in originals}
        dx, dy = group_delta(positions, GRID_STEP * 2, GRID_STEP * 2,
                            anchor=(originals[0].x, originals[0].y))
        copies = tuple(replace(frame, id=uuid4().hex, x=frame.x + dx, y=frame.y + dy) for frame in originals)
        frames = list(self.board.frames)
        index = max(i for i, frame in enumerate(frames) if frame.id in identifiers) + 1
        frames[index:index] = copies
        mapping = {original.id: copy.id for original, copy in zip(originals, copies)}
        links = tuple(StoryLink(mapping[edge.source], mapping[edge.target]) for edge in self.board.links
                      if edge.source in mapping and edge.target in mapping)
        groups = tuple(StoryGroup(title=group.title, members=tuple(mapping[key] for key in group.members))
                       for group in self.board.groups if set(group.members) <= mapping.keys())
        self.changed(replace(self.board, frames=tuple(frames), links=(*self.board.links, *links),
                             groups=(*self.board.groups, *groups)))
        self.refresh()
        self.workspace.navigation.apply_selection({frame.id for frame in copies}, copies[0].id)
        self.page.update(self.content)
        self.workspace.navigation.focus_keyboard()
        await self.persist()

    def confirm_remove_frames(self, identifiers, preserve_flow=False):
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
            updated = graph.detach(updated, positions)
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
        if not self.editable():
            return
        self.lock(True)
        try:
            root = str(self.session.path.parent) if self.session.path else ''
            directory = await asyncio.to_thread(initial_directory, self.image_directory, root)
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
                    self.changed(self.board.change(identifier, image=name, crop_x=0, crop_y=0))
                    self.cards[identifier].set_image(name)
                else:
                    x, y = next_position(self.board.frames)
                    frame = StoryFrame(title=source.stem, image=name, x=x, y=y)
                    self.changed(replace(self.board, frames=(*self.board.frames, frame)))
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
        self.lock(True)
        try:
            root = str(self.session.path.parent) if self.session.path else ''
            directory = await asyncio.to_thread(initial_directory, '', root)
            # O nome informado ao seletor não pode conter separadores de caminho.
            name = ''.join(c for c in self.board.title if c not in '<>:"/\\|?*').strip(' .') or 'storyboard'
            destination = await ft.FilePicker().save_file(dialog_title='Exportar storyboard em PDF',
                file_name=f'{name}.pdf', initial_directory=directory,
                file_type=ft.FilePickerFileType.CUSTOM, allowed_extensions=['pdf'])
            if destination and not self.closing:
                self.notify('Gerando PDF…', 'working')
                saved = await asyncio.to_thread(export_pdf, self.board, self.store, Path(destination))
                self.notify(f'PDF exportado: {saved}', 'success')
        except (OSError, ValueError, RuntimeError) as exc:
            self.notify(f'Não foi possível exportar: {exc}', 'error')
        finally:
            self.lock(False)

    async def deactivate(self):
        """Suspende gestos/player ao sair da aba, preservando documento e histórico."""
        self.workspace.context_menu.dismiss(refocus=False)
        self.workspace.camera_memory.remember()
        self.workspace.grab.cancel(update=False)
        if self.workspace.drag:
            self.workspace.cancel_drag(self.workspace.drag.identifier, update=False)
        self.workspace.box_selection.cancel()
        self.workspace.box_zoom.cancel()
        self.workspace.links.cancel()
        self.workspace.links.cancel_cut()
        self.properties.end_adjust()
        if self.player.opened:
            self.player.close()
        else:
            self.player.dismissed()
        self.workspace.cancel_camera_transition()
        nav = self.workspace.navigation
        nav.reset_keys()
        nav.editing_fields.clear()
        await self.preferences.flush()
        await self.workspace.camera_memory.flush()
        self.active = False

    async def shutdown(self):
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
        await asyncio.to_thread(self.player.audio_transport.close)
        # Aguarda qualquer gravação de recuperação antes de limpar a sessão.
        async with self.save_lock:
            self.closing = True
