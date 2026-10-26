"""Reprodução temporizada por relógio monotônico; usa imagens já em memória."""

import asyncio
from time import monotonic

import flet as ft

from koma.ui.design import APP_PADDING, COMPACT_CONTROL_HEIGHT, ICON_SIZE, MUTED, dialog
from koma.ui.typography import FONT_HEADING, TEXT_SECTION, TEXT_SMALL
from koma.editor.framing import ImageViewport
from koma.editor.subtitle_preview import SubtitlePreview
from koma.editor.timeline import Timeline
from koma.editor.timeline_edit import TimelineEditor
from koma.editor.shortcuts import Action
from koma.ui.timeline_strip import TimelineStrip
from koma.ui.player_layout import PlayerLayout
from koma.ui.player_toolbar import PlayerToolbar
from koma.editor.timeline_media import TimelineMedia
from koma.audio_transport import AudioTransport
from koma.editor.marker_edit import MarkerEditor
from koma.editor.timeline_navigation import adjacent_stop


class AnimaticPlayer:
    def __init__(self, view):
        self.view = view
        self.opened = self.playing = False
        self.dismiss_pending = False
        self.position = 0.0
        self.anchor = 0.0
        self.current = -1
        self.task = None
        self.timeline = None
        self.scene_anchor = None
        self.media = TimelineMedia(self)
        self.audio_transport = AudioTransport()
        self.duration_editor = TimelineEditor(self)
        self.marker_editor = MarkerEditor(self)
        self.strip = TimelineStrip(self, self.duration_editor)
        self.layout = PlayerLayout()
        self.preview = ImageViewport(view, height=400)
        self.subtitles = SubtitlePreview(self)
        self.screen = ft.Container(aspect_ratio=16/9, content=ft.Stack(
            [self.preview.content, self.subtitles.content], fit=ft.StackFit.EXPAND))
        self.caption = ft.Text(size=TEXT_SMALL, font_family=FONT_HEADING, max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS)
        self.clock = ft.Text(size=TEXT_SMALL, color=MUTED)
        self.play = ft.IconButton(icon=ft.Icons.PLAY_ARROW, tooltip='Reproduzir', on_click=self.toggle,
            width=COMPACT_CONTROL_HEIGHT, height=COMPACT_CONTROL_HEIGHT, icon_size=ICON_SIZE)
        self.loop = ft.Checkbox(label='Repetir', value=False, height=COMPACT_CONTROL_HEIGHT)
        self.show_subtitles = ft.Checkbox(label='Legendas', value=True, height=COMPACT_CONTROL_HEIGHT, on_change=self.toggle_subtitles,
            tooltip='Mostrar ou ocultar no player. A inclusão no MP4 é escolhida na exportação.')
        self.previous_button = ft.IconButton(icon=ft.Icons.SKIP_PREVIOUS, on_click=self.previous,
            width=COMPACT_CONTROL_HEIGHT, height=COMPACT_CONTROL_HEIGHT, icon_size=ICON_SIZE)
        self.next_button = ft.IconButton(icon=ft.Icons.SKIP_NEXT, on_click=self.next,
            width=COMPACT_CONTROL_HEIGHT, height=COMPACT_CONTROL_HEIGHT, icon_size=ICON_SIZE)
        transport = ft.Row([self.previous_button, self.play, self.next_button], spacing=0, tight=True)
        self.toolbar = PlayerToolbar(self.caption, self.strip.duration_input.field, transport, self.clock,
            self.strip.fps, self.strip.history_tools, self.strip.zoom_tools)
        self.controls = self.toolbar.commands
        self.preview_slot = ft.Container(content=self.screen, alignment=ft.Alignment.CENTER)
        self.content = ft.Column([self.preview_slot, self.controls, self.strip.content], tight=True, spacing=APP_PADDING,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        self.keyboard = ft.KeyboardListener(content=self.content, autofocus=True)
        self.export_button = ft.TextButton('MP4', icon=ft.Icons.MOVIE_OUTLINED, tooltip='Exportar MP4',
            height=COMPACT_CONTROL_HEIGHT, on_click=view.files.video_from_player)
        self.popup = dialog(title=ft.Text('Animatic'), content=self.keyboard,
            inset_padding=ft.Padding.all(self.layout.dialog_inset),
            title_padding=ft.Padding.only(left=self.layout.content_padding, right=self.layout.content_padding, top=8, bottom=4),
            content_padding=ft.Padding.symmetric(horizontal=self.layout.content_padding, vertical=APP_PADDING),
            actions_padding=ft.Padding.symmetric(horizontal=self.layout.content_padding, vertical=APP_PADDING),
            modal=True, on_dismiss=self.dismissed, actions=[
                self.show_subtitles, self.loop, self.export_button,
                ft.IconButton(icon=ft.Icons.CLOSE, tooltip='Fechar · Esc', on_click=self.close,
                    width=COMPACT_CONTROL_HEIGHT, height=COMPACT_CONTROL_HEIGHT, icon_size=ICON_SIZE)])

    def open(self, e=None):
        if not self.view.editable() or not self.view.board.frames or self.opened or self.dismiss_pending:
            return
        self.timeline = Timeline(self.view.board, self.view.workspace.navigation.selected)
        if not self.timeline.frames:
            self.view.notify('Esta cena não tem quadros ativos. Conecte quadros ou desmute os nodes para reproduzir.' if self.timeline.root
                else 'Selecione um Node Principal ou um quadro conectado a ele para reproduzir a cena.', 'warning')
            return
        self.popup.title = ft.Text(self.timeline.root.title or 'Cena' if self.timeline.root else 'Prévia',
            size=TEXT_SECTION, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
        self.scene_anchor = self.timeline.root.id if self.timeline.root else None
        self.position, self.current = 0, -1
        self.layout.apply(self.view.page, self.content, self.preview_slot)
        self.opened = True
        self.media.cancelled.clear()
        self.playing = False
        self.strip.reset()
        self.render(update=False)
        self.view.page.show_dialog(self.popup)
        self.focus_timeline()

    def focus_timeline(self):
        if self.opened and not self.view.closing:
            self.view.page.run_task(self.keyboard.focus)

    def rebuild_timeline(self):
        self.timeline = Timeline(self.view.board, self.scene_anchor)
        self.position = max(0, min(self.position, self.timeline.total))
        self.current = -1

    @property
    def editing(self):
        return bool(self.duration_editor.drag or self.duration_editor.committing
            or self.marker_editor.drag or self.marker_editor.committing)

    def render(self, update=True):
        if self.timeline is None:
            return
        if self.duration_editor.drag is None and self.timeline.board is not self.view.board:
            self.rebuild_timeline()
        editing = self.editing
        self.play.disabled = editing or not self.timeline.frames
        self.export_button.disabled = editing or not self.view.editable() or not self.timeline.frames
        self.preview.content.visible = bool(self.timeline.frames)
        if not self.timeline.frames:
            self.playing = False
            self.current = -1
            self.caption.value = 'Nenhum quadro ativo nesta cena.'
            self.position = 0
        index = self.timeline.index_at(self.position)
        if self.timeline.frames and index != self.current:
            self.current = index
            frame = self.timeline.frames[index]
            self.preview.set_frame(frame)
            self.subtitles.set_text(frame.subtitle if self.show_subtitles.value else '')
            self.caption.value = f'{index+1:02d} · {frame.title or "Sem título"}'
            self.caption.tooltip = f'{frame.duration * self.view.board.fps:.6g} f · {frame.duration:.6g} s'
        self.clock.value = f'{self.position:.2f} / {self.timeline.total:.2f} s'
        self.play.icon = ft.Icons.PAUSE if self.playing else ft.Icons.PLAY_ARROW
        self.play.tooltip = self.view.keymap.describe('Pausar' if self.playing else 'Reproduzir', Action.PLAY)
        self.previous_button.tooltip = self.view.keymap.describe('Quadro ou marcador anterior', Action.PREVIOUS_STOP)
        self.next_button.tooltip = self.view.keymap.describe('Próximo quadro ou marcador', Action.NEXT_STOP)
        self.previous_button.disabled = self.next_button.disabled = editing or not self.timeline.frames
        self.strip.sync()
        self.audio_transport.update(self.timeline, self.view.store, self.playing and self.opened, self.position)
        if self.audio_transport.error:
            self.view.notify(self.audio_transport.error, 'warning')
            self.audio_transport.error = ''
        if update and self.opened and not self.view.closing:
            self.view.page.update(self.content)

    def toggle_subtitles(self, e=None):
        self.view.preferences.update(show_subtitles=bool(self.show_subtitles.value))
        if not self.opened or not self.timeline or self.current < 0:
            return
        frame = self.timeline.frames[self.current]
        self.subtitles.set_text(frame.subtitle if self.show_subtitles.value else '')
        self.view.page.update(self.content)

    def toggle(self, e=None):
        if not self.opened or self.play.disabled:
            return
        if self.playing:
            self.position = min(self.timeline.total, monotonic()-self.anchor)
            self.playing = False
        else:
            if self.position >= self.timeline.total:
                self.position = 0
            self.anchor = monotonic()-self.position
            self.playing = True
            if self.task is None or self.task.done():
                self.task = self.view.page.run_task(self.tick)
        self.render()
        self.focus_timeline()

    def advance(self, now):
        if not self.playing:
            return
        self.position = max(0, now-self.anchor)
        if self.position >= self.timeline.total:
            if self.loop.value:
                self.position %= self.timeline.total
                self.anchor = now-self.position
            else:
                self.position = self.timeline.total
                self.playing = False
        self.render()

    async def tick(self):
        while self.opened and not self.view.closing:
            if not self.playing:
                return
            self.advance(monotonic())
            await asyncio.sleep(.05)

    def step(self, delta):
        if not self.timeline.frames or self.editing:
            return
        self.playing = False
        self.position = adjacent_stop(self.timeline, self.position, delta)
        self.render()

    def frame_step(self, delta):
        self.strip.navigator.seek(self.position + delta / self.view.board.fps)

    def previous(self, e):
        self.step(-1)
        self.focus_timeline()

    async def key_down(self, e):
        modifiers = {name for field, name in (('ctrl', 'Ctrl'), ('alt', 'Alt'),
            ('shift', 'Shift'), ('meta', 'Meta')) if getattr(e, field, False)}
        action = self.view.keymap.resolve(e.key, modifiers, 'timeline')
        if self.strip.marker_lane.renaming is not None:
            if action == Action.CANCEL:
                self.strip.marker_lane.cancel_rename()
                self.focus_timeline()
            return
        if self.strip.audio_controls.focused:
            if action == Action.CANCEL:
                self.strip.audio_controls.blur()
                self.focus_timeline()
            return
        if self.strip.duration_input.focused:
            if action == Action.CANCEL:
                self.strip.duration_input.cancel()
                self.focus_timeline()
            return
        if action == Action.CANCEL:
            editing = self.editing
            self.duration_editor.cancel()
            self.marker_editor.cancel()
            if editing:
                self.focus_timeline()
            else:
                self.close()
            return
        if self.editing or not self.view.editable():
            return
        if action == Action.PLAY:
            self.toggle()
        elif action == Action.ADD_MARKER:
            await self.media.add_marker()
        elif action == Action.SNAP:
            self.strip.audio_controls.toggle_snap()
        elif action == Action.PREVIOUS_STOP:
            self.step(-1)
        elif action == Action.NEXT_STOP:
            self.step(1)
        elif action == Action.PREVIOUS_FRAME:
            self.frame_step(-1)
        elif action == Action.NEXT_FRAME:
            self.frame_step(1)
        elif action == Action.START:
            self.strip.navigator.seek(0)
        elif action == Action.END:
            self.strip.navigator.seek(self.timeline.total)
        elif action == Action.RENAME_MARKER:
            self.strip.marker_lane.rename()
        elif action == Action.DELETE_MARKER and self.marker_editor.selected:
            await self.media.remove_marker(self.marker_editor.selected)
        elif action == Action.IMPORT_AUDIO:
            await self.media.pick_audio()
        elif action == Action.UNDO:
            await self.strip.undo_edit()
        elif action == Action.REDO:
            await self.strip.redo_edit()
        elif action in (Action.FOCUS, Action.FIT):
            self.strip.fit()

    def next(self, e):
        self.step(1)
        self.focus_timeline()

    def dismissed(self, e=None):
        self.opened = False
        self.media.cancelled.set()
        self.audio_transport.stop()
        self.strip.audio_controls.focused = False
        self.marker_editor.cancel(update=False)
        self.marker_editor.selected = None
        self.strip.marker_lane.cancel_rename()
        self.strip.navigator.end()
        self.strip.duration_input.cancel()
        self.duration_editor.cancel(update=False)
        self.subtitles.clear()
        self.dismiss_pending = False
        self.opened = self.playing = False
        if self.task is not None:
            self.task.cancel()
            self.task = None

    def close(self, e=None):
        self.dismissed()
        self.dismiss_pending = True
        self.view.page.pop_dialog()
