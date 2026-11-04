"""Comandos de documento e exportações de uma única sessão."""

import asyncio
import json
from datetime import datetime
from pathlib import Path

import flet as ft

from koma.ui.menus import menu_item, popup_menu

from koma.ui.design import CONTROL_HEIGHT, MUTED, dialog, input_style
from koma.paths import initial_directory, open_file
from koma.documents.session import DocumentSession
from koma.documents.bundle import destination_stamp as document_stamp
from koma.editor.animatic import Timeline
from koma.exports.video_export import timeline_frame_counts
from koma.exports.video_frames import StoryboardFrames
from koma.exports.encoding import video_progress
from koma.exports.video_runner import VideoRunner, destination_stamp


def file_name(value):
    return ''.join(c for c in value if c not in '<>:"/\\|?*').strip(' .') or 'storyboard'


class StoryboardFiles:
    def __init__(self, view):
        self.view, self.page = view, view.page
        self.directory = str(view.session.path.parent) if view.session.path else ''
        self.runner = VideoRunner(view.settings.directory / 'logs')
        self.cancelled = self.exporting = False
        self.task = None
        self.last_video = None
        self.include_subtitles = True
        self.cancel_button = ft.TextButton('Cancelar exportação', icon=ft.Icons.STOP,
            height=CONTROL_HEIGHT, visible=False, on_click=self.cancel)
        self.open_button = ft.TextButton('Abrir MP4', icon=ft.Icons.OPEN_IN_NEW,
            height=CONTROL_HEIGHT, visible=False, on_click=self.open_video)
        self.actions = ft.Row([self.cancel_button, self.open_button], visible=False, spacing=4)
        self.commands = {
            'new': menu_item('Novo', icon=ft.Icons.NOTE_ADD_OUTLINED, on_click=self.new_document),
            'open': menu_item('Abrir…', icon=ft.Icons.FOLDER_OPEN, on_click=self.open_document),
            'save': menu_item('Salvar', icon=ft.Icons.SAVE_OUTLINED, on_click=self.save_document),
            'save_as': menu_item('Salvar como…', on_click=self.save_as),
            'recover': menu_item('Recuperar…', on_click=self.recover_document),
            'pdf': menu_item('PDF…', icon=ft.Icons.PICTURE_AS_PDF_OUTLINED, on_click=view.export),
            'mp4': menu_item('MP4…', icon=ft.Icons.MOVIE_OUTLINED, on_click=self.video_options),
        }
        self.menu = popup_menu(tooltip='Arquivo', items=list(self.commands.values()))

    async def initial(self, *, exporting=False):
        files = self.view.settings.configuration.values['files']
        folder = files['export_folder' if exporting else 'import_folder']
        return await asyncio.to_thread(initial_directory, folder or self.directory)

    def track_task(self):
        self.task = asyncio.current_task()

    async def choose(self, title, message, choices, *, confirm=None):
        if confirm is not None and confirm not in {key for key, _ in choices}:
            raise ValueError('A ação padrão precisa pertencer às opções do diálogo.')
        future = asyncio.get_running_loop().create_future()
        def dismissed(e=None):
            if not future.done():
                future.set_result('cancel')
        def selected(key):
            def handler(e=None):
                if not future.done():
                    future.set_result(key)
                self.page.pop_dialog()
            return handler
        self.page.show_dialog(dialog(title=ft.Text(title), content=ft.Text(message), modal=True,
            on_confirm=selected(confirm) if confirm is not None else False,
            on_cancel=selected('cancel'),
            on_dismiss=dismissed,
            actions=[ft.TextButton(label, on_click=selected(key)) for key, label in choices]))
        return await future

    async def guard_changes(self):
        if not self.view.dirty:
            return True
        if not self.view.settings.configuration.values['confirmations']['close']:
            saved = await self.view.persist()
            if saved:
                self.view.session.keep_recovery = True
            return saved
        decision = await self.choose('Alterações não salvas',
            f'Projeto: {self.view.board.title or "Sem título"}. Salve as alterações antes de fechá-lo.',
            [('cancel', 'Cancelar'), ('discard', 'Descartar'), ('save', 'Salvar')], confirm='save')
        if decision == 'save':
            return await self._save_document()
        return decision == 'discard'

    async def _save_document(self, save_as=False):
        view = self.view
        view.properties.end_adjust()
        target = view.session.path
        expected = view.session.stamp
        if save_as or target is None:
            selected = await ft.FilePicker().save_file(dialog_title='Salvar documento Koma',
                file_name=(target.name if target else file_name(view.board.title) + '.koma'),
                initial_directory=await self.initial(exporting=True),
                file_type=ft.FilePickerFileType.CUSTOM, allowed_extensions=['koma'])
            if not selected:
                return False
            target = Path(selected).expanduser().resolve().with_suffix('.koma')
            expected = await asyncio.to_thread(document_stamp, target)
            if target == view.session.path:
                expected = view.session.stamp
            elif expected is not None:
                if await self.choose('Substituir documento?', f'O arquivo {target.name} já existe.',
                    [('cancel', 'Cancelar'), ('replace', 'Substituir')]) != 'replace':
                    return False
        board = view.board
        if view.can_save_to is not None and not view.can_save_to(target):
            raise ValueError('Este arquivo já está aberto em outra aba. Escolha outro destino.')
        async with view.save_lock:
            saved = await asyncio.to_thread(view.session.save, board, target, expected_stamp=expected)
        view.session.board = view.board
        self.directory = str(saved.parent)
        if hasattr(view, 'document_saved'):
            view.document_saved(saved)
        await view.persist()
        view.chrome.sync()
        view.notify(f'Documento salvo: {saved}', 'success')
        return True

    async def save_document(self, e=None, *, save_as=False):
        view = self.view
        if view.busy or view.closing or view.load_error:
            return False
        view.lock(True)
        self.track_task()
        try:
            return await self._save_document(save_as)
        except (OSError, ValueError, RuntimeError) as exc:
            view.notify(f'Não foi possível salvar: {exc}', 'error')
            return False
        finally:
            self.task = None
            view.lock(False)

    async def save_as(self, e=None):
        return await self.save_document(save_as=True)

    async def new_document(self, e=None):
        await self.change_document()

    async def open_document(self, e=None):
        await self.change_document(pick=True)

    async def change_document(self, *, pick=False, recovery=None, path=None):
        view = self.view
        if view.busy or view.closing:
            return
        candidate = None
        view.lock(True)
        try:
            if recovery:
                candidate = await asyncio.to_thread(DocumentSession.from_recovery, recovery, view.settings.directory)
            elif path is not None:
                candidate = await asyncio.to_thread(DocumentSession.open, path, view.settings.directory)
            elif pick:
                selected = await ft.FilePicker().pick_files(dialog_title='Abrir documento Koma',
                    allow_multiple=False, initial_directory=await self.initial(),
                    file_type=ft.FilePickerFileType.CUSTOM, allowed_extensions=['koma'])
                if not selected or not selected[0].path:
                    return
                candidate = await asyncio.to_thread(DocumentSession.open, selected[0].path, view.settings.directory)
            else:
                candidate = DocumentSession(view.settings.directory)
            # Novo/Abrir adicionam uma aba; os outros documentos continuam abertos.
            await view.switch_session(candidate)
            candidate = None
        except (OSError, ValueError, RuntimeError) as exc:
            view.notify(f'Não foi possível trocar de documento: {exc}', 'error')
        finally:
            if candidate is not None:
                await asyncio.to_thread(candidate.close)
            if not view.closing:
                view.lock(False)

    async def recover_document(self, e=None):
        if self.view.busy or self.view.closing:
            return
        entries = await asyncio.to_thread(DocumentSession.recoveries, self.view.settings.directory)
        entries = [entry for entry in entries if entry.parent != self.view.session.directory
                   and entry.parent != self.view.session.recovered_from]
        if not entries:
            self.view.notify('Não há sessões anteriores para recuperar.')
            return
        def labels():
            result = []
            for entry in entries:
                try:
                    raw = json.loads(entry.read_text(encoding='utf-8'))
                    title = raw.get('title') or 'Sem título'
                    name = Path(raw['path']).name if raw.get('path') else 'Ainda sem arquivo'
                    date = datetime.fromtimestamp(entry.stat().st_mtime).strftime('%d/%m/%Y %H:%M')
                    result.append((entry, f'{title} · {name} · {date}'))
                except (OSError, ValueError, TypeError):
                    result.append((entry, 'Sessão com recuperação incompleta'))
            return result
        recovery_labels = await asyncio.to_thread(labels)
        future = asyncio.get_running_loop().create_future()
        def selected(path):
            def handler(e=None):
                if not future.done():
                    future.set_result(path)
                self.page.pop_dialog()
            return handler
        def dismissed(e=None):
            if not future.done():
                future.set_result(None)
        self.view.lock(True)
        try:
            self.page.show_dialog(dialog(title=ft.Text('Recuperar sessão'), modal=True, on_dismiss=dismissed,
                on_confirm=False, on_cancel=selected(None),
                content=ft.Column([ft.TextButton(label, on_click=selected(entry)) for entry, label in recovery_labels],
                    scroll=ft.ScrollMode.AUTO, height=240, width=420),
                actions=[ft.TextButton('Cancelar', on_click=selected(None))]))
            choice = await future
        finally:
            self.view.lock(False)
        if choice:
            await self.change_document(recovery=choice)

    def video_options(self, e=None):
        view = self.view
        if not view.editable():
            return
        board, session = view.board, view.session
        timeline = Timeline(board, view.player.scene_anchor if view.player.opened else view.workspace.navigation.selected)
        from koma.exports.sequence import ExportSequence
        from koma.expressions import arithmetic_value
        roots = [frame for frame in board.frames if frame.node_type.starts_scene]
        scope = ft.Dropdown(label='Exportar', value='project' if view.player.project_mode or not timeline.frames else 'current', options=[
            ft.DropdownOption('current', 'Cena atual'), ft.DropdownOption('project', 'Projeto completo'),
            ft.DropdownOption('selected', 'Escolher cenas')], **input_style())
        scenes = [(root, ft.Checkbox(label=root.title or 'Cena', value=True)) for root in roots]
        scene_list = ft.Column([control for _, control in scenes], visible=False, tight=True)
        start = ft.TextField(label='Início (f)', value='0', expand=True, **input_style())
        end = ft.TextField(label='Fim (f)', expand=True, **input_style())
        error = ft.Text(color=ft.Colors.ERROR, visible=False)
        def selection():
            if scope.value == 'current':
                return ExportSequence.from_timelines([timeline])
            return ExportSequence.from_project(board,
                {root.id for root, control in scenes if control.value} if scope.value == 'selected' else None)
        def update_scope(e=None):
            scene_list.visible = scope.value == 'selected'
            start.value, end.value = '0', f'{selection().total * board.fps:.15g}'
            if e is not None:
                self.page.update(scene_list, start, end)
        scope.on_select = update_scope
        for _, control in scenes:
            control.on_change = update_scope
        update_scope()
        name = timeline.root.title if timeline.root else view.board.title
        fps = ft.Text(f'{view.board.fps} FPS · definido nas propriedades do projeto')
        project_fps = view.board.fps
        project_format = view.board.frame_format
        size = ft.Text(f'{project_format.width} × {project_format.height} · {project_format.ratio_label} · formato do projeto')
        subtitles = ft.Checkbox(label='Incluir legendas no MP4', value=self.include_subtitles)
        def choose_subtitles(e=None):
            self.include_subtitles = bool(subtitles.value)
            view.preferences.update(include_subtitles=self.include_subtitles)
        subtitles.on_change = choose_subtitles
        from koma.ui.reference_fields import ReferenceFields
        from koma.ui.collapsible_section import CollapsibleSection
        choices = ReferenceFields(view, on_change=view.player.reference_presentation.refresh)
        def choose_reference_fields(e=None):
            choices.changed(e)
        reference_section = CollapsibleSection(self.page, 'Dados de referência',
            [choices.content],
            expanded=bool(view.preferences.options.reference_fields))
        reference_section.button.tooltip = 'Gravar dados na imagem do MP4. Contagem inicia em 1; duração corresponde ao trecho exportado.'
        async def export(e):
            try:
                if view.board is not board or view.session is not session or not view.editable():
                    raise ValueError('O projeto mudou. Feche e abra novamente as opções de exportação.')
                sequence = selection()
                sequence = sequence.window(arithmetic_value(start.value or '0') / project_fps,
                    arithmetic_value(end.value or '0') / project_fps)
            except ValueError as exc:
                error.value, error.visible = str(exc), True
                self.page.update(error)
                return
            self.page.pop_dialog()
            choose_subtitles()
            choose_reference_fields()
            await self.pick_video(sequence, name if scope.value == 'current' else view.board.title, project_fps, project_format.size,
                include_subtitles=self.include_subtitles, reference_fields=view.preferences.options.reference_fields)
        self.page.show_dialog(dialog(title=ft.Text('Exportar animatic MP4'), on_confirm=export, content=ft.Column([
            scope, scene_list, ft.Row([start, end]), error, fps, size, subtitles, reference_section.content,
        ], width=390, tight=True, spacing=12, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
            scrollable=True, actions=[ft.TextButton('Cancelar', on_click=lambda e: self.page.pop_dialog()),
            ft.FilledButton('Escolher destino', on_click=export)]))

    def video_from_player(self, e=None):
        if not self.view.player.opened:
            return
        self.view.player.playing = False
        self.view.player.render_position()
        self.video_options()

    async def pick_video(self, timeline, name, fps, size, *, include_subtitles=True, reference_fields=()):
        view = self.view
        if not view.editable():
            return
        view.lock(True)
        try:
            from koma.file_defaults import export_name
            suggested = export_name(view, name, timeline)
            selected = await ft.FilePicker().save_file(dialog_title='Salvar animatic MP4', file_name=suggested+'.mp4',
                initial_directory=await self.initial(exporting=True), file_type=ft.FilePickerFileType.CUSTOM, allowed_extensions=['mp4'])
        except (OSError, ValueError, RuntimeError) as exc:
            view.notify(str(exc), 'error')
            return
        finally:
            view.lock(False)
        if selected and not view.closing:
            destination = Path(selected).with_suffix('.mp4').resolve()
            await self.export_video(timeline, destination, fps, size, destination_stamp(destination),
                include_subtitles=include_subtitles, reference_fields=reference_fields)

    async def export_video(self, timeline, destination, fps, size, expected_stamp, *, include_subtitles=True, reference_fields=()):
        view = self.view
        if not view.editable() or not timeline.frames:
            return
        view.properties.end_adjust()
        view.lock(True)
        self.exporting, self.cancelled = True, False
        self.cancel_button.visible, self.open_button.visible = True, False
        self.actions.visible = True
        self.track_task()
        try:
            from koma.editor.node_media import board_assets
            owned = {(getattr(view.store, folder) / name).resolve() for folder, name in board_assets(view.board)}
            if Path(destination).resolve() in owned:
                raise ValueError('Escolha um destino fora dos arquivos de mídia do projeto.')
            counts = await asyncio.to_thread(timeline_frame_counts, timeline, fps)
            view.feedback.progress.value = 0
            view.notify(f'Preparando {len(timeline.frames)} quadros para o MP4…', 'working')
            source = StoryboardFrames(tuple(timeline.frames), view.store, tuple(size), tuple(counts),
                include_subtitles, tuple(getattr(timeline, 'source_offsets', ())),
                tuple(reference_fields), tuple(getattr(timeline, 'references', ())),
                view.settings.configuration.values, media_filter=view.board.media_filter)
            if reference_fields and not source.references:
                from dataclasses import replace
                from koma.exports.reference_overlay import frame_references
                source = replace(source, references=frame_references(timeline))
            def progress(event):
                if self.cancelled or view.closing:
                    return
                view.feedback.progress.value = video_progress(event)
                text = f"{event.get('phase', 'Exportando')} · {event.get('done', 0)}/{event.get('total', 1)}"
                view.notify(text, 'working')
            audio_tracks = []
            for track in timeline.audio_tracks:
                if track.muted or track.volume <= 0:
                    continue
                audio_tracks.append(dict(path=str(view.store.audio / track.asset),
                    start=track.start, volume=track.volume, offset=getattr(track, 'source_offset', 0),
                    duration=track.duration))
            if self.cancelled or view.closing:
                view.notify('Exportação cancelada. O vídeo anterior foi preservado.', 'cancelled')
                return
            quality = {'Alta': 'HIGH', 'Média': 'MEDIUM'}[view.settings.configuration.values['files']['quality']]
            result = await self.runner.run(source, destination, fps, quality, 0, progress,
                expected_destination_stamp=expected_stamp, audio_tracks=audio_tracks)
            if result:
                self.last_video = result
                self.directory = str(result.parent)
                self.open_button.visible = True
                view.notify(f'Animatic MP4 salvo: {result}', 'success')
            else:
                view.notify('Exportação cancelada. O vídeo anterior foi preservado.', 'cancelled')
        except (OSError, ValueError, RuntimeError) as exc:
            view.notify(f'Falha ao exportar o animatic: {exc}', 'error')
        finally:
            self.cancel_button.visible = False
            self.actions.visible = self.open_button.visible
            self.exporting = False
            self.task = None
            view.feedback.sync()
            view.lock(False)

    def cancel(self, e=None):
        self.cancelled = True
        self.runner.cancel()

    async def open_video(self, e=None):
        if self.last_video:
            try:
                await asyncio.to_thread(open_file, self.last_video)
            except (OSError, ValueError) as exc:
                self.view.notify(str(exc), 'error')

    async def shutdown(self):
        self.cancel()
        await self.runner.shutdown()
        if self.task and self.task != asyncio.current_task():
            await asyncio.shield(self.task)
