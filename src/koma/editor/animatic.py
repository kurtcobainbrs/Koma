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
from koma.keymap import key_name
from koma.ui.timeline_strip import TimelineStrip
from koma.ui.player_layout import PlayerLayout
from koma.ui.player_toolbar import PlayerToolbar
from koma.ui.components import toggle_icon
from koma.ui.splitter import Splitter
from koma.editor.timeline_media import TimelineMedia
from koma.audio_transport import AudioTransport
from koma.editor.marker_edit import MarkerEditor
from koma.editor.timeline_navigation import adjacent_stop
from koma.editor.drawing_editor import FrameDrawingEditor
from koma.ui.drawing_surface import DrawingSurface


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
        self.drawing = FrameDrawingEditor(self)
        self.drawing_surface = DrawingSurface(self)
        self.strip = TimelineStrip(self, self.duration_editor)
        self.layout = PlayerLayout()
        self.preview = ImageViewport(view, height=400, show_drawing=False)
        self.subtitles = SubtitlePreview(self)
        self.screen = ft.Container(aspect_ratio=view.board.frame_format.aspect_ratio, content=ft.Stack(
            [self.preview.content, self.drawing_surface.content, self.subtitles.content], fit=ft.StackFit.EXPAND))
        self.caption = ft.Text(size=TEXT_SMALL, font_family=FONT_HEADING, max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS)
        self.clock = ft.Text(size=TEXT_SMALL, color=MUTED)
        self.play = ft.IconButton(icon=ft.Icons.PLAY_ARROW, tooltip='Reproduzir', on_click=self.toggle,
            width=COMPACT_CONTROL_HEIGHT, height=COMPACT_CONTROL_HEIGHT, icon_size=ICON_SIZE)
        self.loop = toggle_icon(ft.Icons.REPEAT, ft.Icons.REPEAT_ON, self.toggle_loop)
        self.show_subtitles = toggle_icon(ft.Icons.SUBTITLES_OFF_OUTLINED, ft.Icons.SUBTITLES,
            self.toggle_subtitles, selected=True)
        self.previous_button = ft.IconButton(icon=ft.Icons.SKIP_PREVIOUS, on_click=self.previous,
            width=COMPACT_CONTROL_HEIGHT, height=COMPACT_CONTROL_HEIGHT, icon_size=ICON_SIZE)
        self.next_button = ft.IconButton(icon=ft.Icons.SKIP_NEXT, on_click=self.next,
            width=COMPACT_CONTROL_HEIGHT, height=COMPACT_CONTROL_HEIGHT, icon_size=ICON_SIZE)
        transport = ft.Row([self.previous_button, self.play, self.next_button], spacing=0, tight=True)
        self.toolbar = PlayerToolbar(self.strip.duration_input.field, transport, self.clock,
            self.strip.fps, self.strip.history_tools, self.strip.zoom_tools,
            [self.show_subtitles, self.loop], self.strip.audio_controls.tools)
        # Reuse the audio footer for frame context instead of adding another band.
        self.strip.footer_context.content = self.caption
        self.controls = self.toolbar.commands
        self.preview_bounds = None
        self.preview_slot = ft.Container(content=self.screen, alignment=ft.Alignment.CENTER,
            on_size_change=self.preview_resized)
        self.preview_splitter = Splitter(view.page, self.preview_slot, horizontal=True, minimum=120, maximum=900)
        self.content = ft.Column([self.preview_slot, self.preview_splitter.content, self.controls, self.strip.content], tight=True, spacing=APP_PADDING,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        self.keyboard = ft.KeyboardListener(content=self.content, autofocus=True)
        self.export_button = ft.OutlinedButton('Exportar MP4', icon=ft.Icons.FILE_UPLOAD_OUTLINED, tooltip='Exportar animatic em MP4',
            height=COMPACT_CONTROL_HEIGHT, on_click=view.files.video_from_player)
        self.title = ft.Text('Animatic', expand=True, size=TEXT_SECTION,
            max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
        self.close_button = ft.IconButton(icon=ft.Icons.CLOSE, tooltip='Fechar · Esc', on_click=self.close,
            width=COMPACT_CONTROL_HEIGHT, height=COMPACT_CONTROL_HEIGHT, icon_size=ICON_SIZE)
        self.popup = dialog(title=ft.Column([
                ft.Row([self.title, self.export_button, self.close_button], spacing=APP_PADDING * 2),
                self.drawing_surface.tools], tight=True, spacing=APP_PADDING,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH), content=self.keyboard,
            inset_padding=ft.Padding.all(self.layout.dialog_inset),
            title_padding=ft.Padding.symmetric(horizontal=self.layout.content_padding, vertical=APP_PADDING),
            content_padding=ft.Padding.symmetric(horizontal=self.layout.content_padding, vertical=APP_PADDING),
            actions_padding=0, modal=True, on_dismiss=self.dismissed, native_actions=False)

    def open(self, e=None):
        if not self.view.editable() or not self.view.board.frames or self.opened or self.dismiss_pending:
            return
        self.timeline = Timeline(self.view.board, self.view.workspace.navigation.selected)
        if not self.timeline.frames:
            self.view.notify('Esta cena não tem quadros ativos. Conecte quadros ou desmute os nodes para reproduzir.' if self.timeline.root
                else 'Selecione um Node Principal ou um quadro conectado a ele para reproduzir a cena.', 'warning')
            return
        self.title.value = self.timeline.root.title or 'Cena' if self.timeline.root else 'Prévia'
        self.scene_anchor = self.timeline.root.id if self.timeline.root else None
        self.position, self.current = 0, -1
        self.layout.apply(self.view.page, self.content, self.preview_slot)
        if self.preview_splitter.user_resized:
            self.preview_slot.expand = False
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

    def fit_preview(self):
        self.screen.aspect_ratio = self.view.board.frame_format.aspect_ratio
        if self.preview_bounds:
            self.screen.width, self.screen.height = self.view.board.frame_format.fit(*self.preview_bounds)

    def preview_resized(self, e):
        if e.width > 0 and e.height > 0 and self.preview_bounds != (e.width, e.height):
            self.preview_bounds = (e.width, e.height)
            self.preview_slot.height = e.height
            self.fit_preview()
            if self.opened:
                self.view.page.update(self.screen)

    def rebuild_timeline(self):
        self.timeline = Timeline(self.view.board, self.scene_anchor)
        self.position = max(0, min(self.position, self.timeline.total))
        self.current = -1

    @property
    def editing(self):
        return bool(self.duration_editor.drag or self.duration_editor.committing
            or self.marker_editor.drag or self.marker_editor.committing
            or self.drawing.drag or self.drawing.committing
            or self.strip.audio_lane.drag.snapshot)

    def render(self, update=True):
        if self.timeline is None:
            return
        self.fit_preview()
        if self.duration_editor.drag is None and self.timeline.board is not self.view.board:
            self.rebuild_timeline()
        if self.drawing.drag and (not self.timeline.frames or
                self.timeline.frames[self.timeline.index_at(self.position)].id != self.drawing.drag.frame.id):
            self.drawing.cancel(update=False)
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
            self.subtitles.set_text(frame.subtitle if self.show_subtitles.selected else '')
            self.caption.value = f'{index+1:02d} · {frame.title or "Sem título"}'
            self.caption.tooltip = f'{frame.duration * self.view.board.fps:.6g} f · {frame.duration:.6g} s'
        self.clock.value = f'{self.position:.2f} / {self.timeline.total:.2f} s'
        self.play.icon = ft.Icons.PAUSE if self.playing else ft.Icons.PLAY_ARROW
        self.play.tooltip = self.view.keymap.describe('Pausar' if self.playing else 'Reproduzir', Action.PLAY)
        self.previous_button.tooltip = self.view.keymap.describe('Quadro ou marcador anterior', Action.PREVIOUS_STOP)
        self.next_button.tooltip = self.view.keymap.describe('Próximo quadro ou marcador', Action.NEXT_STOP)
        self.show_subtitles.tooltip = ('Legendas ligadas · clique para ocultar' if self.show_subtitles.selected
            else 'Legendas desligadas · clique para mostrar')
        self.loop.tooltip = 'Repetir ligado · clique para desligar' if self.loop.selected else 'Repetir desligado · clique para ligar'
        self.previous_button.disabled = self.next_button.disabled = editing or not self.timeline.frames
        self.strip.sync()
        self.drawing_surface.sync()
        self.audio_transport.update(self.timeline, self.view.store, self.playing and self.opened, self.position)
        if self.audio_transport.error:
            self.view.notify(self.audio_transport.error, 'warning')
            self.audio_transport.error = ''
        if update and self.opened and not self.view.closing:
            self.view.page.update(self.content, self.popup.title)

    def render_duration_preview(self, frame):
        """Update timing controls without resending the large preview or canvas."""
        self.caption.tooltip = f'{frame.duration * self.view.board.fps:.6g} f · {frame.duration:.6g} s'
        self.clock.value = f'{self.position:.2f} / {self.timeline.total:.2f} s'
        self.strip.sync()
        if self.opened and not self.view.closing:
            self.view.page.update(self.strip.content, self.controls, self.caption)

    def render_position(self):
        """Seek/playback update only transport and the frames that actually change."""
        if not self.opened or self.view.closing or self.timeline is None:
            return
        if self.timeline.board is not self.view.board or self.current < 0:
            self.render()
            return
        old_index = self.current
        index = self.timeline.index_at(self.position)
        if index != old_index:
            self.render(update=False)
            controls = [self.preview.content, self.subtitles.content, self.caption,
                self.drawing_surface.content, self.drawing_surface.visibility,
                self.strip.duration_input.field,
                *[self.strip.blocks[self.timeline.frames[i].id].box
                    for i in {old_index, index} if 0 <= i < len(self.timeline.frames)]]
        else:
            self.strip.sync_cursor()
            self.clock.value = f'{self.position:.2f} / {self.timeline.total:.2f} s'
            self.play.icon = ft.Icons.PAUSE if self.playing else ft.Icons.PLAY_ARROW
            self.play.tooltip = self.view.keymap.describe('Pausar' if self.playing else 'Reproduzir', Action.PLAY)
            self.audio_transport.update(self.timeline, self.view.store, self.playing, self.position)
            controls = []
        self.view.page.update(self.clock, self.play, self.strip.playhead, self.strip.needle, *controls)

    def toggle_subtitles(self, e=None):
        self.show_subtitles.selected = not self.show_subtitles.selected
        self.view.preferences.update(show_subtitles=bool(self.show_subtitles.selected))
        if not self.opened or not self.timeline or self.current < 0:
            return
        frame = self.timeline.frames[self.current]
        self.subtitles.set_text(frame.subtitle if self.show_subtitles.selected else '')
        self.render()
        self.focus_timeline()

    def toggle_loop(self, e=None):
        self.loop.selected = not self.loop.selected
        self.render()
        self.focus_timeline()

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
            if self.loop.selected:
                self.position %= self.timeline.total
                self.anchor = now-self.position
            else:
                self.position = self.timeline.total
                self.playing = False
        self.render_position()

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
        if self.drawing_surface.picker is not None:
            if action == Action.CANCEL:
                self.drawing_surface.close_picker()
                self.focus_timeline()
            elif key_name(e.key) == 'Enter':
                self.drawing_surface.picker.apply(e)
                self.focus_timeline()
            return
        if self.drawing_surface.focused:
            if action == Action.CANCEL:
                self.drawing_surface.set_width()
                self.focus_timeline()
            return
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
        if self.drawing_surface.tool_menu.opened:
            if action in (Action.DRAWING_TOOLS, Action.CANCEL):
                self.drawing_surface.tool_menu.close()
            return
        if action == Action.CANCEL:
            if not self.editing and self.drawing.selected_index() is not None:
                self.drawing.clear_selection()
                self.render()
                self.focus_timeline()
                return
            editing = self.editing
            self.drawing.cancel()
            self.strip.audio_lane.drag.cancel()
            self.duration_editor.cancel()
            self.marker_editor.cancel()
            if editing:
                self.focus_timeline()
            else:
                self.close()
            return
        if self.editing or not self.view.editable():
            return
        if action == Action.DRAWING_TOOLS:
            await self.drawing_surface.toggle_tools()
        elif action == Action.PLAY:
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
        elif action == Action.DELETE_SELECTION:
            await self.delete_selection()
        elif action == Action.IMPORT_AUDIO:
            await self.media.pick_audio()
        elif action == Action.UNDO:
            await self.strip.undo_edit()
        elif action == Action.REDO:
            await self.strip.redo_edit()
        elif action in (Action.FOCUS, Action.FIT):
            self.strip.fit()

    async def delete_selection(self):
        if self.editing or not self.view.editable():
            return
        if await self.drawing.delete_selected():
            return
        if self.marker_editor.selected:
            await self.media.remove_marker(self.marker_editor.selected)

    def next(self, e):
        self.step(1)
        self.focus_timeline()

    def dismissed(self, e=None):
        self.opened = False
        self.drawing_surface.tool_menu.close()
        self.drawing.cancel(update=False)
        self.drawing.clear_selection()
        self.drawing_surface.reset_inputs()
        self.drawing_surface.focused = False
        self.strip.audio_lane.drag.cancel(update=False)
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
        self.drawing_surface.close_picker()
        self.drawing_surface.tool_menu.close()
        self.dismissed()
        self.dismiss_pending = True
        self.view.page.pop_dialog()
