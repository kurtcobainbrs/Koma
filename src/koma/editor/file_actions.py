"""Comandos de documento e exportações de uma única sessão."""

import asyncio
import json
import tempfile
from datetime import datetime
from pathlib import Path

import flet as ft

from koma.ui.design import CONTROL_HEIGHT, MUTED, dialog, input_style
from koma.paths import initial_directory, open_file
from koma.documents.session import DocumentSession
from koma.documents.bundle import destination_stamp as document_stamp
from koma.editor.animatic import Timeline
from koma.exports.video_export import frame_counts, prepare_frames
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
        self.menu = ft.PopupMenuButton(tooltip='Arquivo', items=[
            ft.PopupMenuItem('Novo', icon=ft.Icons.NOTE_ADD_OUTLINED, on_click=self.new_document),
            ft.PopupMenuItem('Abrir…', icon=ft.Icons.FOLDER_OPEN, on_click=self.open_document),
            ft.PopupMenuItem('Salvar', icon=ft.Icons.SAVE_OUTLINED, on_click=self.save_document),
            ft.PopupMenuItem('Salvar como…', on_click=self.save_as),
            ft.PopupMenuItem('Recuperar sessão…', on_click=self.recover_document),
            ft.PopupMenuItem('Exportar PDF…', icon=ft.Icons.PICTURE_AS_PDF_OUTLINED, on_click=view.export),
            ft.PopupMenuItem('Exportar MP4…', icon=ft.Icons.MOVIE_OUTLINED, on_click=self.video_options),
            ft.PopupMenuItem('Preferências do Blender…', icon=ft.Icons.SETTINGS_OUTLINED, on_click=self.blender_options),
        ])

    async def initial(self):
        return await asyncio.to_thread(initial_directory, self.directory)

    def track_task(self):
        self.task = asyncio.current_task()

    async def choose(self, title, message, choices):
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
            on_dismiss=dismissed,
            actions=[ft.TextButton(label, on_click=selected(key)) for key, label in choices]))
        return await future

    async def guard_changes(self):
        if not self.view.dirty:
            return True
        decision = await self.choose('Alterações não salvas',
            f'Projeto: {self.view.board.title or "Sem título"}. Salve as alterações antes de fechá-lo.',
            [('cancel', 'Cancelar'), ('discard', 'Descartar'), ('save', 'Salvar')])
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
                initial_directory=await self.initial(),
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

    async def change_document(self, *, pick=False, recovery=None):
        view = self.view
        if view.busy or view.closing:
            return
        candidate = None
        view.lock(True)
        try:
            if recovery:
                candidate = await asyncio.to_thread(DocumentSession.from_recovery, recovery, view.settings.directory)
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
                content=ft.Column([ft.TextButton(label, on_click=selected(entry)) for entry, label in recovery_labels],
                    scroll=ft.ScrollMode.AUTO, height=240, width=420),
                actions=[ft.TextButton('Cancelar', on_click=selected(None))]))
            choice = await future
        finally:
            self.view.lock(False)
        if choice:
            await self.change_document(recovery=choice)

    def blender_options(self, e=None):
        if self.view.busy:
            return
        field = ft.TextField(label='Executável do Blender', value=self.view.settings.blender, **input_style())
        error = ft.Text(visible=False, color=ft.Colors.ERROR)
        async def browse(e=None):
            selected = await ft.FilePicker().pick_files(dialog_title='Selecionar Blender', allow_multiple=False)
            if selected and selected[0].path:
                field.value = selected[0].path
                self.page.update(field)
        async def save(e=None):
            value = (field.value or '').strip()
            previous = self.view.settings.blender
            try:
                if value and not Path(value).expanduser().is_file():
                    raise ValueError('Escolha um executável existente do Blender.')
                self.view.settings.blender = str(Path(value).expanduser().resolve()) if value else ''
                await asyncio.to_thread(self.view.settings.save)
                self.page.pop_dialog()
            except (OSError, ValueError) as exc:
                self.view.settings.blender = previous
                error.value, error.visible = str(exc), True
                self.page.update(error)
        self.page.show_dialog(dialog(title=ft.Text('Preferências do Blender'),
            content=ft.Column([field, ft.TextButton('Escolher executável…', on_click=browse),
                ft.Text('Necessário apenas para exportar MP4. O Blender é instalado separadamente.', color=MUTED), error],
                width=520, tight=True),
            actions=[ft.TextButton('Cancelar', on_click=lambda e: self.page.pop_dialog()),
                ft.FilledButton('Salvar', on_click=save)]))

    def video_options(self, e=None):
        view = self.view
        if not view.editable():
            return
        timeline = Timeline(view.board, view.workspace.navigation.selected)
        if not timeline.frames:
            view.notify('Selecione uma cena com quadros para exportar o animatic.', 'warning')
            return
        name = timeline.root.title if timeline.root else view.board.title
        fps = ft.Dropdown(label='FPS', value='24', options=[ft.DropdownOption(str(n)) for n in (24, 25, 30, 60)], **input_style())
        size = ft.Dropdown(label='Resolução', value='1920', options=[
            ft.DropdownOption('1920', '1920 × 1080'), ft.DropdownOption('1280', '1280 × 720')], **input_style())
        subtitles = ft.Checkbox(label='Incluir legendas no MP4', value=self.include_subtitles)
        def choose_subtitles(e=None):
            self.include_subtitles = bool(subtitles.value)
            view.preferences.update(include_subtitles=self.include_subtitles)
        subtitles.on_change = choose_subtitles
        async def export(e):
            self.page.pop_dialog()
            choose_subtitles()
            await self.pick_video(timeline, name, int(fps.value), (int(size.value), 1080 if size.value == '1920' else 720),
                include_subtitles=self.include_subtitles)
        self.page.show_dialog(dialog(title=ft.Text('Exportar animatic MP4'), content=ft.Column([
            ft.Text(f'{name} · {len(timeline.frames)} quadros · {timeline.total:g} s'), fps, size, subtitles,
            ft.Text('Usa o Blender configurado no Koma. Cortes diretos, sem áudio; mantém os enquadramentos.', color=MUTED),
        ], width=390, tight=True, spacing=12, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
            actions=[ft.TextButton('Cancelar', on_click=lambda e: self.page.pop_dialog()),
            ft.FilledButton('Escolher destino', on_click=export)]))

    def video_from_player(self, e=None):
        if not self.view.player.opened:
            return
        self.view.player.close()
        self.video_options()

    async def pick_video(self, timeline, name, fps, size, *, include_subtitles=True):
        view = self.view
        if not view.editable():
            return
        view.lock(True)
        try:
            selected = await ft.FilePicker().save_file(dialog_title='Salvar animatic MP4', file_name=file_name(name)+'.mp4',
                initial_directory=await self.initial(), file_type=ft.FilePickerFileType.CUSTOM, allowed_extensions=['mp4'])
        except (OSError, ValueError, RuntimeError) as exc:
            view.notify(str(exc), 'error')
            return
        finally:
            view.lock(False)
        if selected and not view.closing:
            destination = Path(selected).with_suffix('.mp4').resolve()
            await self.export_video(timeline, destination, fps, size, destination_stamp(destination),
                include_subtitles=include_subtitles)

    async def export_video(self, timeline, destination, fps, size, expected_stamp, *, include_subtitles=True):
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
            counts = frame_counts(timeline.frames, fps)
            blender = Path(view.settings.blender).expanduser().resolve()
            if not blender.is_file():
                raise ValueError('Configure um Blender válido nas preferências do Koma para gerar o MP4.')
            view.feedback.progress.value = 0
            view.notify(f'Preparando {len(timeline.frames)} quadros para o MP4…', 'working')
            with tempfile.TemporaryDirectory(prefix='koma-animatic-') as temporary:
                paths = await asyncio.to_thread(prepare_frames, timeline.frames, view.store, Path(temporary), size,
                    lambda: self.cancelled or view.closing, include_subtitles=include_subtitles)
                if self.cancelled or view.closing:
                    view.notify('Exportação cancelada. O vídeo anterior foi preservado.', 'cancelled')
                    return
                def progress(event):
                    value = video_progress(event)
                    view.feedback.progress.value = value
                    text = f"{event.get('phase', 'Exportando')} · {event.get('done', 0)}/{event.get('total', 1)}"
                    view.notify(text, 'working')
                result = await self.runner.run(blender, paths, destination, fps, 'HIGH', size[0], progress,
                    expected_destination_stamp=expected_stamp, frame_durations=counts)
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
